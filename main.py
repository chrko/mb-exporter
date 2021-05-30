from asyncio import CancelledError

import aiohttp.hdrs
import prometheus_client
from aiohttp import web
from prometheus_client.exposition import choose_encoder

import config
from mb_api import MbCustomer, MbHybridVehicle

customer = MbCustomer(client_id=config.client_id, client_secret=config.client_secret)

my_hybrid = MbHybridVehicle(customer, config.vin)

routes = web.RouteTableDef()


@routes.get("/metrics")
async def metrics(request: web.Request):
    if not customer.authorized:
        raise web.HTTPFound(customer.authorization_url()[0])
    encoder, content_type = choose_encoder(request.headers['accept'])
    output = encoder(prometheus_client.REGISTRY)
    return web.Response(
        body=output,
        headers={aiohttp.hdrs.CONTENT_TYPE: content_type},
    )


@routes.get("/oauth.redirect")
async def metrics(request: web.Request):
    customer.fetch_token(**request.query)
    customer.persist()

    if not my_hybrid.running():
        my_hybrid.start()

    raise web.HTTPFound("/metrics")


async def fetch_hybrid(_):
    my_hybrid.start()
    yield
    my_hybrid.stop()
    try:
        await my_hybrid.continuous_refresh_task
    except CancelledError:
        pass


app = web.Application()
app.add_routes(routes)
app.cleanup_ctx.append(fetch_hybrid)

web.run_app(app, host="127.0.0.1")
