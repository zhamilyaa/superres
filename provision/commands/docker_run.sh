docker run  \
	--env-file .env  \
	--shm-size="8g"  \
	--volume "/etc/group:/etc/group:ro"  \
	--volume "/etc/passwd:/etc/passwd:ro"  \
	--volume "/etc/shadow:/etc/shadow:ro"  \
	--volume "/etc/sudoers.d:/etc/sudoers.d:ro"  \
	--env ENV_FOR_DYNACONF=development  \
	--env C_FORCE_ROOT=1  \
	--env MPLCONFIGDIR=/Users/zhamilya/Desktop/storage/caches  \
	--env GDAL_CACHEMAX=256  \
	--env NUMEXPR_MAX_THREADS=8  \
	--network superres_network  \
	--volume /Users/zhamilya/Desktop/storage/caches:/Users/zhamilya/Desktop/storage/caches  \
	--volume /Users/zhamilya/Desktop/storage/sr:/Users/zhamilya/Desktop/storage/sr  \
	--volume /home/zhamilya/PycharmProjects/superres:/home/zhamilya/PycharmProjects/superres  \
	--workdir /home/zhamilya/PycharmProjects/superres "$@"