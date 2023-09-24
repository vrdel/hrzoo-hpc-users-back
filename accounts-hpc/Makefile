container_name = hrzoo-ldapclient

sdist:
	python setup.py sdist

clean-contenv:
	python setup.py clean --all
	rm -rf build/
	rm -rf dist
	rm -rf accounts-hpc.egg-info/

clean:
	docker exec -u user -t $(container_name) bash -c 'source /opt/hrzoo-accounts-hpc/bin/activate && cd /home/user/accounts-hpc-source/ && python setup.py clean --all'
	docker exec -u user -t $(container_name) bash -c 'source /opt/hrzoo-accounts-hpc/bin/activate && cd /home/user/accounts-hpc-source/ && rm -rf build/'
	docker exec -u user -t $(container_name) bash -c 'source /opt/hrzoo-accounts-hpc/bin/activate && cd /home/user/accounts-hpc-source/ && rm -rf dist/'
	docker exec -u user -t $(container_name) bash -c 'source /opt/hrzoo-accounts-hpc/bin/activate && cd /home/user/accounts-hpc-source/ && rm -rf accounts-hpc/'

devel-wheel:
	docker exec -u user -t $(container_name) bash -c 'source /opt/hrzoo-accounts-hpc/bin/activate && cd /home/user/accounts-hpc-source/ && make clean-contenv && python setup.py egg_info --tag-date --tag-build=dev bdist_wheel'

prod-wheel:
	docker exec -u user -t $(container_name) bash -c 'source /opt/hrzoo-accounts-hpc/bin/activate && cd /home/user/accounts-hpc-source/ && make clean-contenv && python setup.py bdist_wheel'
