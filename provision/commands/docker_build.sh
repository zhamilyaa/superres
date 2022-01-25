docker image build -t superres-production:latest  \
	--target builder  \
	--build-arg USER_ID=1000  \
	--build-arg GROUP_ID=1000  \
	--build-arg USERNAME=ubuntu  \
	--build-arg PROJECT_DIR=/home/ubuntu/egistic/superres /home/ubuntu/egistic/superres