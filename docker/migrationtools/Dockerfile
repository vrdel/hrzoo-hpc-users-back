FROM centos:7
MAINTAINER dvrcic@srce.hr
ARG BASEDN
ARG MAIL
RUN groupadd user -g 1000 && useradd -u 1000 -g 1000 user -m -d /home/user -s /bin/zsh
RUN yum -y update; yum clean all
RUN \
    yum -y install \
      procps-ng \
      git \
      migrationtools \
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
      rpmdevtools \
      sudo \
      vim \
      wget \
      yum-utils \
      zsh
RUN pip install -U pip; pip3 install -U pip
RUN passwd -d root
VOLUME [ "/sys/fs/cgroup" ]
RUN echo "user ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
RUN echo "Defaults  env_keep += \"PYTHONPATH\"" >> /etc/sudoers
USER user
WORKDIR /home/user
RUN sudo yum install -y openldap-servers openldap-clients
RUN sudo usermod -a -G adm user
RUN sudo usermod -a -G adm ldap
RUN sudo sed -r -i "s/padl.com/${MAIL}/g" /usr/share/migrationtools/migrate_common.ph; \
    sudo sed -r -i "s/^.DEFAULT_BASE.*$/\$DEFAULT_BASE = \"${BASEDN}\";/g" /usr/share/migrationtools/migrate_common.ph
RUN /usr/share/migrationtools/migrate_passwd.pl /etc/passwd /home/user/passwd.ldif
RUN /usr/share/migrationtools/migrate_group.pl /etc/group /home/user/group.ldif
CMD ["/bin/zsh"]
