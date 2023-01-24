from setuptools import setup

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
   name='DynamoDBInterface',
   version='1.2.2',
   description='Python Interface to Streamline Access to DynamoDB database tables.',
   long_description=long_description,
   author='Pakkapol Lailert',
   author_email='booklailert@gmail.com',
   packages=['DynamoDBInterface'],
   install_requires=['boto3'],
)