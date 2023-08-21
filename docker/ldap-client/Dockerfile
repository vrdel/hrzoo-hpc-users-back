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
      gcc \
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
      openssh-server \
      passwd \
      procps-ng \
      python3-devel \
      python3-pip \
      python3-setuptools \
      python39-devel \
      ripgrep \
      rsync \
      rpmdevtools \
      sudo \
      sqlite \
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
    openldap-devel \
    oddjob-mkhomedir
RUN pip install -U pip; pip3 install -U pip
RUN passwd -d root
VOLUME [ "/sys/fs/cgroup" ]
RUN sed -r -i 's/(^Defaults.*always_set_home)/# \1/' /etc/sudoers
RUN echo -e "user ALL=(ALL) NOPASSWD: ALL\nDefaults env_keep += \"HOME\"" >> /etc/sudoers
USER user
WORKDIR /home/user
RUN sudo python3.9 -m venv /opt/hrzoo-ldapsync
COPY ldap-conf/ /home/user/ldap-conf/
COPY certs/ /home/user/certs/
RUN mkdir /home/user/rpms/
COPY rpms/* /home/user/rpms/
RUN curl -sfL https://git.io/chezmoi | sh
COPY chezmoi-config-apply.sh /home/user
RUN sudo dnf localinstall -y /home/user/rpms/*
RUN sudo cp certs/root.cert /etc/pki/ca-trust/source/anchors \
    && sudo update-ca-trust
RUN sudo cp ldap-conf/etc_openldap/ldap.conf /etc/openldap/
RUN sudo authselect select --force sssd with-mkhomedir
RUN sudo cp ldap-conf/pubkey/etc_ldap.conf /etc/ldap.conf \
    && sudo cp ldap-conf/pubkey/etc_sshd_config /etc/ssh/sshd_config
RUN sudo cp ldap-conf/sudo/etc_nsswitch.conf /etc/nsswitch.conf \
    && sudo cp ldap-conf/sudo/etc_sssd.conf /etc/sssd/sssd.conf \
    && sudo cp ldap-conf/sudo/etc_sudo-ldap.conf /etc/sudo-ldap.conf
CMD ["/sbin/init"]
