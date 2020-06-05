import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="once",
    version="0.0.1",

    description="An one-time file sharing personal service",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="author",

    package_dir={"": "once"},
    packages=setuptools.find_packages(where="once"),

    install_requires=[
        "aws-cdk.core==1.44.0",
    ],

    python_requires=">=3.6",

    classifiers=[
        "Development Status :: 4 - Beta",

        "Intended Audience :: Developers",

        "License :: OSI Approved :: Apache Software License",

        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",

        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",

        "Typing :: Typed",
    ],
)
