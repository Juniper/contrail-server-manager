all:
	@echo "Making Tar ball"
rpm:
	@echo "RPM"
	mkdir -p ~/rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
	cp smgr.spec ~/rpmbuild/SPECS
	rpmbuild -bb ~/rpmbuild/SPECS/smgr.spec

