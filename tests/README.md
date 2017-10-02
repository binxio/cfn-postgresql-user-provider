# test
Before you can test this code, start a local postgres docker container.

```
docker run -d \
      -p 5432:5432 \
      --env POSTGRES_USER=postgres \
      --env POSTGRES_PASSWORD=password \
      --env POSTGRES_DB=postgres \
      postgres:9.6
```
