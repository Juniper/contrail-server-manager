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
	cp contrail-server-manager.spec ~/rpmbuild/SPECS
	rpmbuild -bb ~/rpmbuild/SPECS/contrail-server-manager.spec
	cp ~/rpmbuild/RPMS/noarch/contrail_server-manager-1.0-1.noarch.rpm ~/rpmbuild/RPMS/noarch/contrail_server-manager-1.0-1_$(commit_id).noarch.rpm

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
	cp contrail-server-manager-client.spec ~/rpmbuild/SPECS
	rpmbuild -bb ~/rpmbuild/SPECS/contrail-server-manager-client.spec

client-deb:
	(cd debian-contrail-smgr-client; fakeroot debian/rules binary)
clean-client-deb:
	(cd debian-contrail-smgr-client; fakeroot debian/rules clean)

client-tar:
	tar cvfz server_manager_client.tar.gz client/*.py client/*.json client/*.ini client/server-manager utils/create_smgr_db.py
	cp server_manager_client.tar.gz ~/rpmbuild/RPMS/noarch	
clean:
	(cd debian-contrail-smgr; fakeroot debian/rules clean)


