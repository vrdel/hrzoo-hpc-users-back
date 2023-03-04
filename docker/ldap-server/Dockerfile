FROM redhat/ubi8:8.6
ARG RHUSER
ARG RHPASS
MAINTAINER dvrcic@srce.hr
RUN groupadd user -g 1000 && useradd -u 1000 -g 1000 user -m -d /home/user -s /bin/zsh
RUN dnf -y update; dnf clean all
RUN \
    dnf -y install \
			procps-ng \
      git \
      glibc-all-langpacks \
      iproute \
      make \
      iputils \
      bind-utils \
      hostname \
      net-tools \
      passwd \
      python3-devel \
      python3-pip \
      python3-setuptools \
      sudo \
      vim \
      wget \
      yum-utils \
      zsh
RUN pip install -U pip; pip3 install -U pip
RUN passwd -d root
VOLUME [ "/sys/fs/cgroup" ]
RUN echo "user ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
RUN echo "Defaults	env_keep += \"PYTHONPATH\"" >> /etc/sudoers
USER user
WORKDIR /home/user
RUN curl -sfL https://git.io/chezmoi | sh
RUN sudo subscription-manager register --username ${RHUSER} --password ${RHPASS} && sudo subscription-manager attach --auto
RUN sudo subscription-manager repos --enable codeready-builder-for-rhel-8-$(arch)-rpms
RUN sudo dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm
RUN sudo dnf install -y vim ripgrep procps-ng make ctags ack passwd mc make vifm git fortune-mod ack the_silver_searcher ncurses-compat-libs
RUN sudo wget -q https://repo.symas.com/configs/SOLDAP/rhel8/release26.repo -O /etc/yum.repos.d/soldap-release26.repo
RUN sudo dnf update -y && sudo dnf install -y symas-openldap-clients symas-openldap-servers oddjob-mkhomedir
CMD ["/sbin/init"]
