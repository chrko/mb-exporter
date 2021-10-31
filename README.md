# mb-exporter

This is a prometheus exporter using the APIs provided by Mercedes-Benz. You can subscribe to these APIs and use them only for your own car(
s) (BYOCAR = bring your own car).

## How to use

1. Goto https://developer.mercedes-benz.com/ and login
2. Jump to the [console](https://developer.mercedes-benz.com/console) and create a project dedicated to use with this exporter.
3. Fill in the required details.
4. Click on "Add product" and add the following products. Each with the options "get for free" and "BYOCAR".
    1. Electric Vehicle Status
    2. Fuel Status
    3. Pay As You Drive Insurance
    4. Vehicle Lock Status
    5. Vehicle Status
5. Click on subscribe and back to project page afterwards
6. Generate credentials and save the client id and especially the client secret to a secure location. The client secret cannot be displayed
   again and maybe only regenerated.
7. Adapt the redirect URL. E.g. running this exporter on your local computer or using a port forwarding
   use `http://localhost:8080/oauth.redirect`.
8. Put the client id, the client secret and your cars VIN into a file named `config.py`:
   ```python
   client_id = "my-client-id"
   client_secret = "my-client-secret"
   vin = "my-vin"
   ```

Afterwards you have the option to use the docker image: https://hub.docker.com/r/chrko/mb-exporter

```shell
docker run --detach \
  --rm \
  --name mb-exporter \
  --pull always \
  --publish 8080:8080/tcp \
  --volume /home/mb-exporter/config.py:/mb-exporter/src/config.py \
  --volume /home/mb-exporter/state/state.json:/mb-exporter/state.json \
  chrko/mb-exporter
```

On the first run or after issues with the authentication, you must go to [localhost:8080/oauth.auth](http://localhost:8080/oauth.auth).
There maybe the need to empty `state.json` ***before*** launching the exporter.

```shell
cat > ~mb-exporter/state/state.json < /dev/null
```

## Contributions

Contributions in the form of issues or pull requests are welcome, but please note that this intended to fit my personal needs.

## License

This project is licensed under the terms of Mozilla Public License 2.0.
