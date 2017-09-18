include Makefile.mk

NAME=cfn-dbuser-provider
AWS_REGION=eu-central-1

help:
	@echo 'make                 - builds a zip file to target/.'
	@echo 'make release         - builds a zip file and deploys it to s3.'
	@echo 'make clean           - the workspace.'
	@echo 'make test            - execute the tests, requires a working AWS connection.'
	@echo 'make deploy-provider - deploys the provider.'
	@echo 'make delete-provider - deletes the provider.'
	@echo 'make demo            - deploys the provider and the demo cloudformation stack.'
	@echo 'make delete-demo     - deletes the demo cloudformation stack.'

deploy:
	aws s3 --region $(AWS_REGION) \
		cp target/$(NAME)-$(VERSION).zip \
		s3://binxio-public-$(AWS_REGION)/lambdas/$(NAME)-$(VERSION).zip 
	aws s3 --region $(AWS_REGION) cp \
		s3://binxio-public-$(AWS_REGION)/lambdas/$(NAME)-$(VERSION).zip \
		s3://binxio-public-$(AWS_REGION)/lambdas/$(NAME)-latest.zip 
	aws s3api --region $(AWS_REGION) \
		put-object-acl --bucket binxio-public-$(AWS_REGION) \
		--acl public-read --key lambdas/$(NAME)-$(VERSION).zip 
	aws s3api --region $(AWS_REGION) \
		put-object-acl --bucket binxio-public-$(AWS_REGION) \
		--acl public-read --key lambdas/$(NAME)-latest.zip 

do-push: deploy

do-build: local-build

local-build: src/*.py venv requirements.txt
	mkdir -p target/content 
	pip install --quiet -t target/content -r requirements.txt
	# installing lambda psycopg2 binaries 
	if [ ! -d target/awslambda-psycopg2 ] ; then \
		git clone https://github.com/jkehler/awslambda-psycopg2 target/awslambda-psycopg2 ; \
		(cd target/awslambda-psycopg2 ; git checkout ed3a6f93bf0fc93f90a4dd28adbb651e825deeff ); \
	fi
	rm -rf target/content/psycopg2*
	cp -r target/awslambda-psycopg2/with_ssl_support/psycopg2 target/content	
	# copy the sources 	
	cp -r src/* target/content
	# set the permissions, as AWS cannot read the files otherwise :-(
	find target/content -type d | xargs  chmod ugo+rx
	find target/content -type f | xargs  chmod ugo+r 
	cd target/content && zip --quiet -9r ../../target/$(NAME)-$(VERSION).zip  *
	chmod ugo+r target/$(NAME)-$(VERSION).zip

venv: requirements.txt
	virtualenv venv  && \
	. ./venv/bin/activate && \
	pip install --quiet --upgrade pip && \
	pip install --quiet -r requirements.txt 
	
clean:
	rm -rf venv target
	rm -rf src/*.pyc tests/*.pyc

test: venv
	jq . cloudformation/*.json > /dev/null
	. ./venv/bin/activate && \
	pip install --quiet -r requirements.txt -r test-requirements.txt && \
	cd src && \
	nosetests --nologcapture ../tests/*.py 

autopep:
	autopep8 --experimental --in-place --max-line-length 132 src/*.py tests/*.py

deploy-provider:
	@set -x ;if aws cloudformation get-template-summary --stack-name $(NAME) >/dev/null 2>&1 ; then \
		export CFN_COMMAND=update; \
	else \
		export CFN_COMMAND=create; \
	fi ;\
	export VPC_ID=$$(aws ec2  --output text --query 'Vpcs[?IsDefault].VpcId' describe-vpcs) ; \
        export SUBNET_IDS=$$(aws ec2 --output text --query Subnets[*].SubnetId \
                                describe-subnets --filters Name=vpc-id,Values=$$VPC_ID | tr '\t' ','); \
	export SG_ID=$$(aws ec2 --output text --query "SecurityGroups[*].GroupId" \
				describe-security-groups --group-names default  --filters Name=vpc-id,Values=$$VPC_ID); \
	([[ -z $$VPC_ID ]] || [[ -z $$SUBNET_IDS ]] || [[ -z $$SG_ID ]]) && \
		echo "Either there is no default VPC in your account, less then two subnets or no default security group available in the default VPC" && exit 1 ; \
	echo "$$CFN_COMMAND provider in default VPC $$VPC_ID, subnets $$SUBNET_IDS using security group ($$SG_ID)." ; \
	aws cloudformation $$CFN_COMMAND-stack \
		--capabilities CAPABILITY_IAM \
		--stack-name cfn-dbuser-provider \
		--template-body file://cloudformation/cfn-custom-resource-provider.json  \
		--parameters ParameterKey=VPC,ParameterValue=$$VPC_ID \
			     ParameterKey=Subnets,ParameterValue=\"$$SUBNET_IDS\" \
			     ParameterKey=SecurityGroup,ParameterValue=$$SG_ID ;\
	aws cloudformation wait stack-$$CFN_COMMAND-complete --stack-name $(NAME) ;

delete-provider:
	aws cloudformation delete-stack --stack-name $(NAME)
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)

demo: 
	@if aws cloudformation get-template-summary --stack-name $(NAME)-demo >/dev/null 2>&1 ; then \
		export CFN_COMMAND=update; \
	else \
		export CFN_COMMAND=create; \
	fi ;\
	export VPC_ID=$$(aws ec2  --output text --query 'Vpcs[?IsDefault].VpcId' describe-vpcs) ; \
        export SUBNET_IDS=$$(aws ec2 --output text --query Subnets[*].SubnetId \
                                describe-subnets --filters Name=vpc-id,Values=$$VPC_ID | tr '\t' ','); \
        export SG_ID=$$(aws ec2 --output text --query "SecurityGroups[*].GroupId" \
                                describe-security-groups --group-names default  --filters Name=vpc-id,Values=$$VPC_ID); \
        ([[ -z $$VPC_ID ]] || [[ -z $$SUBNET_IDS ]] || [[ -z $$SG_ID ]]) && \
                echo "Either there is no default VPC in your account, \
		no two subnets or no default security group available in the default VPC" && exit 1 ; \
	aws cloudformation $$CFN_COMMAND-stack --stack-name $(NAME)-demo \
		--template-body file://cloudformation/demo-stack.json  \
		--parameters 	ParameterKey=VPC,ParameterValue=$$VPC_ID \
				ParameterKey=Subnets,ParameterValue=\"$$SUBNET_IDS\" \
				ParameterKey=SecurityGroup,ParameterValue=$$SG_ID ;\
	aws cloudformation wait stack-$$CFN_COMMAND-complete --stack-name $(NAME)-demo ;

delete-demo:
	aws cloudformation delete-stack --stack-name $(NAME)-demo 
	aws cloudformation wait stack-delete-complete  --stack-name $(NAME)-demo

