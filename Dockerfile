	#FROM phusion/baseimage:focal-1.0.0-amd64 as base
FROM nvidia/cuda:11.2.0-runtime-ubuntu20.04 as base
#FROM nvcr.io/nvidia/cuda:11.1-devel-ubuntu20.04 as base
MAINTAINER Zhamilya Saparova, zhamilya.saparova@nu.edu.kz

ENV LANG=C.UTF-8 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Almaty \
    \
    VIRTUAL_ENV=/opt/venv \
    PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # pip
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    # poetry
    # https://python-poetry.org/docs/configuration/#using-environment-variables
#    POETRY_VERSION=1.1.4 \
    # make poetry install to this location
    POETRY_HOME="/opt/poetry" \
    # make poetry create the virtual environment in the project's root
    # it gets named `.venv`
    POETRY_VIRTUALENVS_IN_PROJECT=false \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    CPLUS_INCLUDE_PATH=/usr/include/gdal \
    C_INCLUDE_PATH=/usr/include/gdal

ENV PATH="$POETRY_HOME/bin:$VIRTUAL_ENV/bin:$PATH"
ENV FLASK_APP=app.__main__

COPY . .

RUN apt-get update -y && apt-get install -y --no-install-recommends \
    nano git\
    build-essential \
    python3.8-dev \
    software-properties-common \
    gdal-bin libgdal-dev \
    swig potrace \
    wget unzip file curl \
    libpq-dev libspatialindex-dev \
    libsm6 libxext6 libxrender-dev ffmpeg libgl1-mesa-dev \
    libeccodes0 \
    python3-pip python3-venv &&\
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone &&\
    python3 -m venv $VIRTUAL_ENV &&\
    curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python3 - &&\
    pip3 install --no-cache-dir -U pip wheel setuptools numpy &&\
#    pip3 install --global-option=build_ext \
#                --global-option="-I/usr/include/gdal" \
#                GDAL==$(gdal-config --version) &&\
    curl https://rclone.org/install.sh | bash &&\
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*


FROM base as builder

ARG USER_ID
ARG GROUP_ID
ARG USERNAME
ARG PROJECT_DIR
RUN groupadd -g ${GROUP_ID} ${USERNAME} &&\
    useradd -l -u ${USER_ID} -g ${USERNAME} ${USERNAME} &&\
    install -d -m 0755 -o ${USERNAME} -g ${USERNAME} /home/${USERNAME} &&\
    chown --changes --silent --no-dereference --recursive \
     ${USER_ID}:${GROUP_ID} \
        /home/${USERNAME}

COPY provision/roles/lgblkb/files/poetry_cache/* ./
RUN poetry install
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    python3-tk
COPY pyproject.toml poetry.lock ./
RUN poetry install
RUN pip3 install --no-cache-dir torchvision==0.10.0+cu111 torchaudio==0.9.0 -f https://download.pytorch.org/whl/torch_stable.html &&\
    pip3 install --no-cache-dir kedro

RUN pip install tensorflow

RUN pip install flask

CMD [ "python", "-m" , "flask", "run", "--host=0.0.0.0"]


USER ${USERNAME}
