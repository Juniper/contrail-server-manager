all:
	@echo "Making Tar ball"
rpm:
	@echo "RPM"
	$(eval commit_id=$(shell git log --format="%H" | head -n1))
	@echo git_log is $(commit_id)
	mkdir -p ~/rpmbuild/BUILD
	mkdir -p ~/rpmbuild/RPMS
	mkdir -p ~/rpmbuild/SOURCES
	mkdir -p ~/rpmbuild/SPECS
	mkdir -p ~/rpmbuild/SRPMS
	cp contrail_smgr.spec ~/rpmbuild/SPECS
	rpmbuild -bb ~/rpmbuild/SPECS/contrail_smgr.spec
	cp ~/rpmbuild/RPMS/noarch/contrail_smgr-1.0-1.noarch.rpm ~/rpmbuild/RPMS/noarch/contrail_smgr-1.0-1_$(commit_id).noarch.rpm
deb:
	(cd debian-contrail-smgr; fakeroot debian/rules binary)

client-rpm:
	@echo "Client-RPM"
	$(eval commit_id=$(shell git log --format="%H" | head -n1))
	@echo git_log is $(commit_id)
	mkdir -p ~/rpmbuild/BUILD
	mkdir -p ~/rpmbuild/RPMS
	mkdir -p ~/rpmbuild/SOURCES
	mkdir -p ~/rpmbuild/SPECS
	mkdir -p ~/rpmbuild/SRPMS
	cp contrail_smgr_client.spec ~/rpmbuild/SPECS
	rpmbuild -bb ~/rpmbuild/SPECS/contrail_smgr_client.spec

client-deb:
	(cd debian-contrail-smgr-client; fakeroot debian/rules binary)
client-tar:
	
clean:
	(cd debian-contrail-smgr; fakeroot debian/rules clean)


