from setuptools import find_packages, setup

setup(
    name="arag",
    version="0.6.6",
    packages=find_packages(),
    install_requires=[
        "openai",
        "pydantic",
        "numpy",
        "scikit-learn",
        "tiktoken",
        "pyyaml",
        "requests"
    ],
    author="newport solutions",
    author_email="contact@newport.ro",
    private=True,
    url="https://github.com/Newport-Labs/arag-agent",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)