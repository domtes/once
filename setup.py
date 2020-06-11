import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="once",
    description="A one-time file sharing personal service, running serverless on AWS",
    version="0.1.0",
    url="https://github.com/domtes/once",
    author="Domenico Testa",
    author_email="domenico.testa@gmail.com",
    long_description=long_description,
    long_description_content_type="text/markdown",

    python_requires=">=3.6",
    install_requires=[
        "click",
        "pygments",
        "requests"
    ],

    package_dir={'': 'client'},
    py_modules=['once'],
    entry_points={
        'console_scripts': ['once=once:share']
    },

    classifiers=[
        "Development Status :: 4 - Beta",

        "Intended Audience :: Developers",

        "License :: OSI Approved :: MIT License",

        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",

        "Topic :: File Sharing",
        "Topic :: Utilities",

        "Typing :: Typed",
    ],
)
