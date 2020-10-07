FROM python:3

RUN useradd --no-log-init -m codegrade

RUN apt-get update && apt-get install -y pandoc libxmlsec1-dev lxc-dev

COPY ./requirements.txt /requirements.txt

RUN pip install -r requirements.txt
RUN pip install pypandoc
RUN pip install git+http://github.com/CodeGra-de/openapi-python-client.git@4fde2c3861ac62a5a5401c3ee34d160bac4378a3
RUN rm /requirements.txt

ENV DEBUG=true
ENV PROJECT_NAME_OVERRIDE=codegrade
ENV PACKAGE_NAME_OVERRIDE=codegrade
ENV PYTHONPATH=

ENTRYPOINT ["bash", "-c"]
