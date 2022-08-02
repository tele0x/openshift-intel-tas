FROM registry.access.redhat.com/ubi8/ubi

LABEL maintainer="Intel Corporation"

LABEL com.redhat.component="ubi8-container" \
      name="collectd"
LABEL summary="Provides collectd for TAS"
LABEL io.k8s.display-name="Intel TAS collectd"
LABEL io.openshift.tags="tas collectd"

RUN dnf install -y --setopt=tsflags=nodocs --nogpgcheck --disableplugin=subscription-manager python3 python3-devel \
http://mirror.centos.org/centos/8-stream/BaseOS/x86_64/os/Packages/OpenIPMI-libs-2.0.31-3.el8.x86_64.rpm \
http://mirror.centos.org/centos/8-stream/BaseOS/x86_64/os/Packages/libmicrohttpd-0.9.59-2.el8.x86_64.rpm \
https://vault.centos.org/centos/8/opstools/x86_64/collectd-5/Packages/c/collectd-5.11.0-2.el8.x86_64.rpm \
https://vault.centos.org/centos/8/opstools/x86_64/collectd-5/Packages/c/collectd-ipmi-5.11.0-2.el8.x86_64.rpm \
https://vault.centos.org/centos/8/opstools/x86_64/collectd-5/Packages/c/collectd-pmu-5.11.0-2.el8.x86_64.rpm \
https://vault.centos.org/centos/8/opstools/x86_64/collectd-5/Packages/c/collectd-python-5.11.0-2.el8.x86_64.rpm \
http://mirror.centos.org/centos/7/os/x86_64/Packages/intel-cmt-cat-3.0.1-1.el7.x86_64.rpm \
https://vault.centos.org/centos/8/opstools/x86_64/collectd-5/Packages/c/collectd-rdt-5.11.0-2.el8.x86_64.rpm \
https://vault.centos.org/centos/8/opstools/x86_64/collectd-5/Packages/c/collectd-hugepages-5.11.0-2.el8.x86_64.rpm \
https://vault.centos.org/centos/8/opstools/x86_64/collectd-5/Packages/c/collectd-turbostat-5.11.0-2.el8.x86_64.rpm \
https://vault.centos.org/centos/8/opstools/x86_64/collectd-5/Packages/c/collectd-write_http-5.11.0-2.el8.x86_64.rpm \
https://vault.centos.org/centos/8/opstools/x86_64/collectd-5/Packages/c/collectd-write_prometheus-5.11.0-2.el8.x86_64.rpm \
https://mirrors.bupt.edu.cn/centos/8-stream/opstools/x86_64/collectd-5/Packages/j/jevents-109-2.el8s.x86_64.rpm 
RUN dnf clean all && rm -fr /var/cache/dnf

RUN pip3 install python-config
RUN ln /usr/bin/python3 /usr/bin/python
USER root

# Config
RUN mkdir /usr/share/collectd/python/
COPY pkgpower.py /usr/share/collectd/python/
COPY download_event.py /root/
RUN python /root/download_event.py
#COPY collectd.conf /etc/collectd.d/collectd.conf
#ENTRYPOINT ["/usr/sbin/collectd -C /etc/collectd.d/collectd.conf"]
