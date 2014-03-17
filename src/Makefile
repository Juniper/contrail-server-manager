all:
	@echo "Making Tar ball"
rpm:
	@echo "RPM 1"
	$(eval commit_id=$(shell git log --format="%H" | head -n1))
	@echo git_log is $(commit_id)
	mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
	cp smgr.spec ~/rpmbuild/SPECS
	rpmbuild -bb ~/rpmbuild/SPECS/smgr.spec
	cp ~/rpmbuild/RPMS/noarch/server_mgr-1.0-1.noarch.rpm ~/rpmbuild/RPMS/noarch/server_mgr-1.0-1_$(commit_id).noarch.rpm

