from setuptools import setup, find_packages

setup(
    name="omni_chat",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "google-generativeai>=0.3.0",
        "python-dotenv>=1.0.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "omni-chat=omni_chat.cli.repl:main",
        ],
    },
)
