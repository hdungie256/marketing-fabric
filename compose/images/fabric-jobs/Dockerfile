FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY pyproject.toml .
RUN pip install --no-cache-dir -U "pip>=25.1" && pip install --no-cache-dir --group jobs

RUN cd "$(python -c 'import os, pyspark; print(os.path.dirname(pyspark.__file__))')/jars" \
    && for jar in \
        io/delta/delta-spark_2.12/3.3.3/delta-spark_2.12-3.3.3.jar \
        io/delta/delta-storage/3.3.3/delta-storage-3.3.3.jar \
        org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar \
        com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar \
        org/postgresql/postgresql/42.7.7/postgresql-42.7.7.jar \
        io/openlineage/openlineage-spark_2.12/1.53.0/openlineage-spark_2.12-1.53.0.jar; \
       do curl -fsSLO --retry 5 --retry-all-errors "https://repo1.maven.org/maven2/$jar" || exit 1; done

COPY fabric_control fabric_control
COPY pipelines pipelines
COPY contracts contracts
COPY governance governance
COPY migrations migrations
COPY sources sources
COPY compose/pg-init compose/pg-init

ENV PYTHONPATH=/srv PYTHONUNBUFFERED=1
