include Makefile.mk

NAME=cfn-postgresql-user-provider
AWS_REGION=eu-central-1
S3_BUCKET_PREFIX=binxio-public
S3_BUCKET=$(S3_BUCKET_PREFIX)-$(AWS_REGION)

ALL_REGIONS=$(shell printf "import boto3\nprint('\\\n'.join(map(lambda r: r['RegionName'], boto3.client('ec2').describe_regions()['Regions'])))\n" | python | grep -v '^$(AWS_REGION)$$')

help:
	@echo 'make                 - builds a zip file to target/.'
	@echo 'make release         - builds a zip file and deploys it to s3.'
	@echo 'make clean           - the workspace.'
	@echo 'make test            - execute the tests, requires a working AWS connection.'
	@echo 'make deploy	    - lambda to bucket $(S3_BUCKET)'
	@echo 'make deploy-all-regions - lambda to all regions with bucket prefix $(S3_BUCKET_PREFIX)'
	@echo 'make deploy-provider - deploys the provider.'
	@echo 'make delete-provider - deletes the provider.'
	@echo 'make demo            - deploys the provider and the demo cloudformation stack.'
	@echo 'make delete-demo     - deletes the demo cloudformation stack.'

deploy: target/$(NAME)-$(VERSION).zip
	aws s3 --region $(AWS_REGION) \
		cp --acl \
		public-read target/$(NAME)-$(VERSION).zip \
		s3://$(S3_BUCKET)/lambdas/$(NAME)-$(VERSION).zip 
	aws s3 --region $(AWS_REGION) \
		cp --acl public-read \
		s3://$(S3_BUCKET)/lambdas/$(NAME)-$(VERSION).zip \
		s3://$(S3_BUCKET)/lambdas/$(NAME)-latest.zip 

deploy-all-regions: deploy
	@for REGION in $(ALL_REGIONS); do \
		echo "copying to region $$REGION.." ; \
		aws s3 --region $(AWS_REGION) \
			cp --acl public-read \
			s3://$(S3_BUCKET_PREFIX)-$(AWS_REGION)/lambdas/$(NAME)-$(VERSION).zip \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-$(VERSION).zip; \
		aws s3 --region $$REGION \
			cp  --acl public-read \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-$(VERSION).zip \
			s3://$(S3_BUCKET_PREFIX)-$$REGION/lambdas/$(NAME)-latest.zip; \
	done

do-push: deploy

do-build: target/$(NAME)-$(VERSION).zip

target/$(NAME)-$(VERSION).zip: src/*.py requirements.txt
	mkdir -p target
	docker build --platform linux/x86_64 --build-arg ZIPFILE=$(NAME)-$(VERSION).zip -t $(NAME)-lambda:$(VERSION) -f Dockerfile.lambda . && \
		ID=$$(docker create $(NAME)-lambda:$(VERSION) /bin/true) && \
		docker export $$ID | (cd target && tar -xvf - $(NAME)-$(VERSION).zip) && \
		docker rm -f $$ID && \
		chmod ugo+r target/$(NAME)-$(VERSION).zip

venv: requirements.txt
	virtualenv -p python3.9 venv  && \
	. ./venv/bin/activate && \
	pip install --quiet --upgrade pip && \
	pip install --quiet -r requirements.txt

clean:
	rm -rf venv target
	rm -rf src/*.pyc tests/*.pyc src/__pycache__ tests/__pycache__

test-templates:
	for i in $$PWD/cloudformation/*; do \
		aws cloudformation validate-template --template-body file://$$i > /dev/null || exit 1; \
	done

test: venv
	. ./venv/bin/activate && \
	pip install --quiet -r requirements.txt -r test-requirements.txt && \
	cd src && \
        PYTHONPATH=$(PWD)/src pytest ../tests/test*.py

autopep:
	autopep8 --experimental --in-place --max-line-length 132 src/*.py tests/*.py

deploy-provider:
	@export VPC_ID=$$(aws ec2  --output text --query 'Vpcs[?IsDefault].VpcId' describe-vpcs) ; \
        export SUBNET_IDS=$$(aws ec2 --output text --query 'RouteTables[?Routes[?GatewayId == null]].Associations[].SubnetId' \
                                describe-route-tables --filters Name=vpc-id,Values=$$VPC_ID | tr '\t' ','); \
	export SG_ID=$$(aws ec2 --output text --query "SecurityGroups[*].GroupId" \
				describe-security-groups --group-names default  --filters Name=vpc-id,Values=$$VPC_ID); \
	([[ -z $$VPC_ID ]] || [[ -z $$SUBNET_IDS ]] || [[ -z $$SG_ID ]]) && \
		echo "Either there is no default VPC in your account, no private subnets or no default security group available in the default VPC" && exit 1 ; \
	echo "deploy provider in default VPC $$VPC_ID, private subnets $$SUBNET_IDS using security group $$SG_ID." ; \
	aws cloudformation deploy \
		--capabilities CAPABILITY_IAM \
		--stack-name $(NAME) \
		--template ./cloudformation/cfn-resource-provider.yaml  \
		--parameter-overrides VPC=$$VPC_ID Subnets=$$SUBNET_IDS SecurityGroup=$$SG_ID

delete-provider:
	aws cloudformation delete-stack --stack-name $(NAME)
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)

demo: 
	@export VPC_ID=$$(aws ec2  --output text --query 'Vpcs[?IsDefault].VpcId' describe-vpcs) ; \
        export SUBNET_IDS=$$(aws ec2 --output text --query 'RouteTables[?Routes[?GatewayId == null]].Associations[].SubnetId' \
                                describe-route-tables --filters Name=vpc-id,Values=$$VPC_ID | tr '\t' ','); \
        export SG_ID=$$(aws ec2 --output text --query "SecurityGroups[*].GroupId" \
                                describe-security-groups --group-names default  --filters Name=vpc-id,Values=$$VPC_ID); \
	echo "deploy demo in default VPC $$VPC_ID, private subnets $$SUBNET_IDS using security group $$SG_ID." ; \
        ([[ -z $$VPC_ID ]] || [[ -z $$SUBNET_IDS ]] || [[ -z $$SG_ID ]]) && \
                echo "Either there is no default VPC in your account, no private subnets or no default security group available in the default VPC" && exit 1 ; \
	aws cloudformation deploy --stack-name $(NAME)-demo \
		--template ./cloudformation/demo-stack.yaml  \
		--parameter-overrides VPC=$$VPC_ID Subnets=$$SUBNET_IDS SecurityGroup=$$SG_ID


delete-demo:
	aws cloudformation delete-stack --stack-name $(NAME)-demo
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)-demo

deploy-pipeline: 
	aws cloudformation deploy \
                --capabilities CAPABILITY_IAM \
                --stack-name $(NAME)-pipeline \
                --template-file ./cloudformation/cicd-pipeline.yaml \
                --parameter-overrides \
                        S3BucketPrefix=$(S3_BUCKET_PREFIX)
