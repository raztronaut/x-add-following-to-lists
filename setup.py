from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="twitter-list-manager",
    version="0.1.0",
    author="",  # Add your name
    author_email="",  # Add your email
    description="A tool to manage Twitter following lists using twikit",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",  # Add your repository URL
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "twikit",
    ],
    entry_points={
        "console_scripts": [
            "twitter-list-manager=bulk_list_manager.example:main",
        ],
    },
) 