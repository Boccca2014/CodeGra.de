FROM python:3.8

RUN useradd --no-log-init -m codegrade

RUN apt-get update && apt-get install -y pandoc libxmlsec1-dev lxc-dev

COPY ./requirements.txt /requirements.txt

RUN pip install -r requirements.txt
RUN pip install pypandoc
RUN pip install git+http://github.com/CodeGra-de/openapi-python-client.git@711573eedb0d384de0c107a4315bc97cfeeb3eb6
RUN rm /requirements.txt

ENV DEBUG=true
ENV PROJECT_NAME_OVERRIDE=codegrade
ENV PACKAGE_NAME_OVERRIDE=codegrade
ENV PYTHONPATH=

ENTRYPOINT ["bash", "-c"]
