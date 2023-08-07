FROM rockylinux:8
MAINTAINER dvrcic@srce.hr
RUN groupadd user -g 1000 && useradd -u 1000 -g 1000 user -m -d /home/user -s /bin/zsh
RUN dnf -y install epel-release && dnf -y makecache && dnf -y update
RUN \
    dnf -y install \
      ack \
      bind-utils \
      ctags \
      git \
      git \
      glibc-all-langpacks \
      glibc-all-langpacks \
      hostname \
      iproute \
      iputils \
      make \
      man \
      mc \
      ncurses-compat-libs \
      net-tools \
      nmap \
      passwd \
      procps-ng \
      python3-devel \
      python3-pip \
      python3-setuptools \
      ripgrep \
      rpmdevtools \
      sudo \
      supervisor \
      telnet \
      the_silver_searcher \
      vifm \
      vim \
      wget \
      yum-utils \
      zsh
RUN sed -r -i 's/enabled=0/enabled=1/g' /etc/yum.repos.d/Rocky-PowerTools.repo
RUN dnf makecache -y && sudo dnf -y install \
  sssd \
  sssd-ldap \
  authselect \
  openldap-clients \
  openldap-servers \
  oddjob-mkhomedir
RUN pip install -U pip; pip3 install -U pip
RUN passwd -d root
VOLUME [ "/sys/fs/cgroup" ]
RUN sed -r -i 's/(^Defaults.*always_set_home)/# \1/' /etc/sudoers
RUN echo -e "user ALL=(ALL) NOPASSWD: ALL\nDefaults env_keep += \"HOME\"" >> /etc/sudoers
USER user
WORKDIR /home/user
COPY ldap-conf/ /home/user/ldap-conf/
RUN mkdir /home/user/rpms/
COPY rpms/* /home/user/rpms/
RUN curl -sfL https://git.io/chezmoi | sh
RUN sudo dnf localinstall -y /home/user/rpms/*
RUN sudo cp \
    /home/user/ldap-conf/pubkey/openssh-lpk-openldap.ldif /home/user/ldap-conf/pubkey/openssh-lpk-openldap.schema /etc/openldap/schema
RUN sudo cp \
    /home/user/ldap-conf/pubkey/sudo.schema /home/user/ldap-conf/pubkey/sudo.ldif /etc/openldap/schema
CMD ["sudo", "/usr/bin/supervisord", "-nc",  "/etc/supervisord.conf"]
