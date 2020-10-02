FROM python:3

RUN useradd --no-log-init -m codegrade

RUN apt-get update && apt-get install -y pandoc libxmlsec1-dev lxc-dev

USER codegrade
WORKDIR /home/codegrade
ENV PATH="/home/codegrade/.local/bin:${PATH}"
COPY --chown=codegrade:codegrade ./requirements.txt requirements.txt

RUN pip install --user -r requirements.txt
RUN pip install --user pypandoc pyyaml
RUN pip install --user git+http://github.com/CodeGra-de/openapi-python-client.git@7785a52ea392ddf69553677d4c7d667ca8219c28

ENV DEBUG=true
ENV PROJECT_NAME_OVERRIDE=codegrade
ENV PACKAGE_NAME_OVERRIDE=codegrade
ENV PYTHONPATH=
CMD cd /app && \
        make build_swagger && \
        cd api_libs/python && \
        rm -rf codegrade && \
        openapi-python-client --config ./config.yaml generate --path /app/swagger.json
