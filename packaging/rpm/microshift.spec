# parameters that must be provided via --define , or fixed into the spec file:
# global version 4.7.0
# global release 2021_08_31_224727
# global commit 81264d0ebb17fef06eff9ec7d4f2a81631c6b34a

%{!?commit:
# DO NOT MODIFY: the value on the line below is sed-like replaced by openshift/doozer
%global commit 0000000000000000000000000000000000000000
}

# golang specifics
%global golang_version 1.18
#debuginfo not supported with Go
%global debug_package %{nil}
# modifying the Go binaries breaks the DWARF debugging
%global __os_install_post %{_rpmconfigdir}/brp-compress

# SELinux specifics
%global selinuxtype targeted
%define selinux_policyver 3.14.3-67
%define container_policyver 2.167.0-1
%define container_policy_epoch 2
%define microshift_relabel_files() \
   mkdir -p /var/hpvolumes; \
   mkdir -p /var/run/kubelet; \
   mkdir -p /var/lib/kubelet/pods; \
   mkdir -p /var/run/secrets/kubernetes.io/serviceaccount; \
   restorecon -R /var/hpvolumes; \
   restorecon -R /var/run/kubelet; \
   restorecon -R /var/lib/kubelet/pods; \
   restorecon -R /var/run/secrets/kubernetes.io/serviceaccount


# Git related details
%global shortcommit %(c=%{commit}; echo ${c:0:7})

Name: microshift
Version: %{version}
Release: %{release}%{dist}
Summary: MicroShift service
License: ASL 2.0
URL: https://github.com/openshift/microshift
Source0: https://github.com/openshift/microshift/archive/%{commit}/microshift-%{shortcommit}.tar.gz

ExclusiveArch: x86_64 aarch64

BuildRequires: gcc
BuildRequires: golang >= %{golang_version}
BuildRequires: make
BuildRequires: policycoreutils
BuildRequires: systemd

Requires: cri-o
Requires: cri-tools
Requires: iptables
Requires: microshift-selinux
Requires: microshift-networking
Requires: conntrack-tools
Requires: sos

%{?systemd_requires}

%description
The MicroShift package provides an OpenShift Kubernetes distribution optimized for small form factor and edge computing.

%package selinux
Summary: SELinux policies for MicroShift
BuildRequires: selinux-policy >= %{selinux_policyver}
BuildRequires: selinux-policy-devel >= %{selinux_policyver}
Requires: container-selinux >= %{container_policy_epoch}:%{container_policyver}
BuildArch: noarch
%{?selinux_requires}

%description selinux
The MicroShift SELinux package provides the SELinux policy modules required by MicroShift.

%package networking
Summary: Networking components for MicroShift
Requires: openvswitch2.17
Requires: NetworkManager
Requires: NetworkManager-ovs
Requires: jq

%description networking
The MicroShift Networking package provides the networking components necessary for the MicroShift default CNI driver.

%prep

%setup -n microshift-%{commit}

%build

GOOS=linux

%ifarch %{arm} aarch64
GOARCH=arm64
%endif

%ifarch x86_64
GOARCH=amd64
%endif

# if we have git commit/tag/state to be embedded in the binary pass it down to the makefile
%if %{defined embedded_git_commit}
make _build_local GOOS=${GOOS} GOARCH=${GOARCH} EMBEDDED_GIT_COMMIT=%{commit} EMBEDDED_GIT_TAG=%{embedded_git_tag} EMBEDDED_GIT_TREE_STATE=%{embedded_git_tree_state} MICROSHIFT_VERSION=%{version}
%else
make _build_local GOOS=${GOOS} GOARCH=${GOARCH} MICROSHIFT_VERSION=%{version} EMBEDDED_GIT_COMMIT=%{commit}
%endif

cp ./_output/bin/${GOOS}_${GOARCH}/microshift ./_output/microshift

# SELinux modules build

cd packaging/selinux
make

%install

install -d %{buildroot}%{_bindir}
install -p -m755 ./_output/microshift %{buildroot}%{_bindir}/microshift
install -p -m755 hack/cleanup.sh %{buildroot}%{_bindir}/cleanup-all-microshift-data

restorecon -v %{buildroot}%{_bindir}/microshift

install -d -m755 %{buildroot}%{_sysconfdir}/crio/crio.conf.d

%ifarch %{arm} aarch64
install -p -m644 packaging/crio.conf.d/microshift_arm64.conf %{buildroot}%{_sysconfdir}/crio/crio.conf.d/microshift.conf
%endif

%ifarch x86_64
install -p -m644 packaging/crio.conf.d/microshift_amd64.conf %{buildroot}%{_sysconfdir}/crio/crio.conf.d/microshift.conf
%endif

install -p -m644 packaging/crio.conf.d/microshift-ovn.conf %{buildroot}%{_sysconfdir}/crio/crio.conf.d/microshift-ovn.conf

install -d -m755  %{buildroot}%{_sysconfdir}/NetworkManager/conf.d
install -p -m644  packaging/network-manager-conf/microshift-nm.conf %{buildroot}%{_sysconfdir}/NetworkManager/conf.d/microshift-nm.conf

install -d -m755 %{buildroot}/%{_unitdir}
install -p -m644 packaging/systemd/microshift.service %{buildroot}%{_unitdir}/microshift.service

install -d -m755 %{buildroot}/%{_sysconfdir}/microshift
install -p -m644 packaging/microshift/config.yaml %{buildroot}%{_sysconfdir}/microshift/config.yaml.default

# Memory tweaks to the OpenvSwitch services
mkdir -p -m755 %{buildroot}%{_sysconfdir}/systemd/system/ovs-vswitchd.service.d
mkdir -p -m755 %{buildroot}%{_sysconfdir}/systemd/system/ovsdb-server.service.d
install -p -m644 packaging/systemd/microshift-ovs-vswitchd.conf %{buildroot}%{_sysconfdir}/systemd/system/ovs-vswitchd.service.d/microshift-cpuaffinity.conf
install -p -m644 packaging/systemd/microshift-ovsdb-server.conf %{buildroot}%{_sysconfdir}/systemd/system/ovsdb-server.service.d/microshift-cpuaffinity.conf

# this script and systemd service configures openvswitch to properly operate with OVN
install -p -m644 packaging/systemd/microshift-ovs-init.service %{buildroot}%{_unitdir}/microshift-ovs-init.service
install -p -m755 packaging/systemd/configure-ovs.sh %{buildroot}%{_bindir}/configure-ovs.sh
install -p -m755 packaging/systemd/configure-ovs-microshift.sh %{buildroot}%{_bindir}/configure-ovs-microshift.sh

mkdir -p -m755 %{buildroot}/var/run/kubelet
mkdir -p -m755 %{buildroot}/var/lib/kubelet/pods
mkdir -p -m755 %{buildroot}/var/run/secrets/kubernetes.io/serviceaccount

install -d %{buildroot}%{_datadir}/selinux/packages/%{selinuxtype}
install -m644 packaging/selinux/microshift.pp.bz2 %{buildroot}%{_datadir}/selinux/packages/%{selinuxtype}

%post

%systemd_post microshift.service

# only for install, not on upgrades
if [ $1 -eq 1 ]; then
	# if crio was already started, restart it so it will catch /etc/crio/crio.conf.d/microshift.conf
	systemctl is-active --quiet crio && systemctl restart --quiet crio || true
fi

%post selinux

%selinux_modules_install -s %{selinuxtype} %{_datadir}/selinux/packages/%{selinuxtype}/microshift.pp.bz2
if /usr/sbin/selinuxenabled ; then
    %microshift_relabel_files
fi

%postun selinux

if [ $1 -eq 0 ]; then
    %selinux_modules_uninstall -s %{selinuxtype} microshift
fi

%posttrans selinux

%selinux_relabel_post -s %{selinuxtype}

%post networking
# setup ovs / ovsdb optimization to avoid full pre-allocation of memory
sed -i -n -e '/^OPTIONS=/!p' -e '$aOPTIONS="--no-mlockall"' /etc/sysconfig/openvswitch
%systemd_post microshift-ovs-init.service
systemctl is-active --quiet NetworkManager && systemctl restart --quiet NetworkManager || true
systemctl enable --now --quiet openvswitch || true

%preun networking
%systemd_preun microshift-ovs-init.service

%preun

%systemd_preun microshift.service


%files

%license LICENSE
%{_bindir}/microshift
%{_bindir}/cleanup-all-microshift-data
%{_unitdir}/microshift.service
%{_sysconfdir}/crio/crio.conf.d/microshift.conf
%config(noreplace) %{_sysconfdir}/microshift/config.yaml.default

%files selinux

/var/run/kubelet
/var/lib/kubelet/pods
/var/run/secrets/kubernetes.io/serviceaccount
%{_datadir}/selinux/packages/%{selinuxtype}/microshift.pp.bz2
%ghost %{_sharedstatedir}/selinux/%{selinuxtype}/active/modules/200/microshift

%files networking

%{_sysconfdir}/crio/crio.conf.d/microshift-ovn.conf

%{_sysconfdir}/NetworkManager/conf.d/microshift-nm.conf

%{_sysconfdir}/systemd/system/ovs-vswitchd.service.d/microshift-cpuaffinity.conf
%{_sysconfdir}/systemd/system/ovsdb-server.service.d/microshift-cpuaffinity.conf

# OpensvSwitch oneshot configuration script which handles ovn-k8s gateway mode setup
%{_unitdir}/microshift-ovs-init.service
%{_bindir}/configure-ovs.sh
%{_bindir}/configure-ovs-microshift.sh

# Use Git command to generate the log and replace the VERSION string
# LANG=C git log --date="format:%a %b %d %Y" --pretty="tformat:* %cd %an <%ae> VERSION%n- %s%n" packaging/rpm/microshift.spec
%changelog
* Wed Dec 07 2022 Gregory Giguashvili <ggiguash@redhat.com> 4.12.0
- Update the summaries and descriptions of MicroShift RPM packages

* Tue Dec 06 2022 Patryk Matuszak <pmatusza@redhat.com> 4.12.0
- Add commit macro and embed it into binary

* Wed Nov 30 2022 Patryk Matuszak <pmatusza@redhat.com> 4.12.0
- Pass version macro to Makefile

* Wed Nov 30 2022 Gregory Giguashvili <ggiguash@redhat.com> 4.12.0
- Change the config.yaml file name to allow its overwrite by users

* Mon Nov 28 2022 Patryk Matuszak <pmatusza@redhat.com> 4.12.0
- Use commit time & sha for RPM and exec

* Fri Nov 25 2022 Gregory Giguashvili <ggiguash@redhat.com> 4.12.0
- Install sos utility with MicroShift and document its usage

* Mon Oct 24 2022 Zenghui Shi <zshi@redhat.com> 4.12.0
- Add arch specific crio conf

* Fri Sep 30 2022 Frank A. Zdarsky <fzdarsky@redhat.com> 4.12.0
- Update openswitch version to 2.17

* Wed Aug 31 2022 Doug Hellmann <dhellmann@redhat.com> 4.10.0
- Remove experimental comments from RPM description
- Add example config file to rpm

* Wed Aug 31 2022 Gregory Giguashvili <ggiguash@redhat.com> 4.10.0
- Fix RPM post install script not to return error when crio is not running
- Co-authored-by: Dan Clark <danielmclark@gmail.com>

* Wed Aug 31 2022 Patryk Matuszak <pmatusza@redhat.com> 4.10.0
- Removed hostpath-provisioner

* Tue Aug 02 2022 Zenghui Shi <zshi@redhat.com> 4.10.0
- Fix openvswitch issues when MicroShift service is disabled

* Thu Jul 28 2022 Ricardo Noriega <rnoriega@redhat.com> 4.10.0
- Add NetworkManager configuration file

* Tue Jul 26 2022 Miguel Angel Ajo Pelayo <majopela@redhat.com> 4.10.0
- Move crio.conf.d/microshift-ovn.conf to microshift-networking

* Tue Jul 26 2022 Zenghui Shi <zshi@redhat.com> 4.10.0
- Restart NetworkManager before OVS configuration

* Fri Jul 22 2022 Miguel Angel Ajo Pelayo <majopela@redhat.com> 4.10.0
- Add the jq dependency

* Thu Jul 21 2022 Miguel Angel Ajo Pelayo <majopela@redhat.com> 4.10.0
- Remove ovs duplicated services to set CPUAffinity with systemd .d dirs

* Thu Jul 21 2022 Ricardo Noriega <rnoriega@redhat.com> 4.10.0
- Adding microshift-ovn.conf with CRI-O network and workload partitioning

* Wed Jul 20 2022 Miguel Angel Ajo Pelayo <majopela@redhat.com> 4.10.0
- Add microshift-ovs-init script as oneshot during boot

* Tue Jul 19 2022 Miguel Angel Ajo <majopela@redhat.com> 4.10.0
- Adding the microshift-ovs-init systemd service and script which initializes br-ex and connects
  the main interface through it.

* Tue Jul 12 2022 Miguel Angel Ajo <majopela@redhat.com> 4.10.0
- Adding the networking subpackage to support ovn-networking
- Adding virtual openvswitch systemd files with CPUAffinity=0
- Setting OVS_USER_OPT to --no-mlockall in /etc/sysconfig/openvswitch

* Tue May 24 2022 Ricardo Noriega <rnoriega@redhat.com> 4.10.0
- Adding hostpath-provisioner.service to set SElinux policies to the volumes directory

* Fri May 6 2022 Sally O'Malley <somalley@redhat.com> 4.10.0
- Update required golang version to 1.17

* Mon Feb 7 2022 Ryan Cook <rcook@redhat.com> 4.8.0
- Selinux directory creation and labeling

* Wed Feb 2 2022 Ryan Cook <rcook@redhat.com> 4.8.0
- Define specific selinux policy version to help manage selinux package

* Wed Feb 2 2022 Miguel Angel Ajo <majopela@redhat.com> 4.8.0
- Remove the microshift-containerized subpackage, our docs explain how to download the .service file,
  and it has proven problematic to package this.
- Fix the microshift.service being overwritten by microshift-containerized, even when the non-containerized
  package only is installed.

* Thu Nov 4 2021 Miguel angel Ajo <majopela@redhat.com> 4.8.0
- Add microshift-containerized subpackage which contains the microshift-containerized systemd
  definition.

* Thu Nov 4 2021 Miguel Angel Ajo <majopela@redhat.com> 4.8.0
- Include the cleanup-all-microshift-data script for convenience


* Thu Sep 23 2021 Miguel Angel Ajo <majopela@redhat.com> 4.7.0
- Support commit based builds
- workaround rpmbuild with no build in place support
- add missing BuildRequires on systemd and policycoreutils

* Mon Sep 20 2021 Miguel Angel Ajo <majopela@redhat.com> 4.7.0
- Initial packaging
