#!/usr/bin/env python
from setuptools import setup, find_packages
from typing import Dict, List
import os
import re
from codecs import open


here = os.path.abspath(os.path.dirname(__file__))
PROJECT_NAME = "FantaStat"
PROJECT_TITLE = "FantaStat"


def get_pipfile_requirements() -> List[str]:
    with open("Pipfile") as pipfile:
        packages_list = []
        found_packages = False
        end_packages = False
        for line in pipfile:
            if "[packages]" in line:
                found_packages = True
            elif found_packages and line == "\n":
                end_packages = True
            elif found_packages and not end_packages:
                package = line.split("=")[0].strip()
                if "https://" not in line:
                    if package != PROJECT_TITLE:
                        package_details = line[line.find("=") + 1 :].strip()
                        path = None
                        version = None
                        if "path" in package_details:
                            path_matches = re.search(r"path=\"(.+)\"", package_details)
                            path = path_matches.group(1)
                        elif "version" in package_details:
                            version_matches = re.search(
                                r"version *= *\"([\w\.>=<,\*]+)\"", package_details
                            )
                            version = version_matches.group(1)
                        else:
                            version = line.split('"')[1].strip()
                        if path is None:
                            if version != "*":
                                packages_list.append(package + version)
                            else:
                                packages_list.append(package)
                else:
                    link = re.search("(?P<url>https?://[^\s]+)", line).group("url")
                    # Exclude curly bracket
                    if link[-2:] == '"}':
                        link = link[:-2]
                        link = os.path.expandvars(link)

                    packages_list.append(package + " @ git+" + link)

    return packages_list


about: Dict[str, str] = {}

with open(os.path.join(here, PROJECT_NAME, "__version__.py"), "r", "utf-8") as f:
    exec(f.read(), about)

with open("README.md", "r", "utf-8") as f:
    readme = f.read()

if __name__ == "__main__":
    setup(
        name=about["__title__"],
        version=about["__version__"],
        description=about["__description__"],
        long_description=readme,
        long_description_content_type="text/markdown",
        author=about["__author__"],
        author_email=about["__author_email__"],
        entry_points = {
			"console_scripts": [
                # "fslauncher1 = FantaStat.launcher.launcher1:main",
			]
		},
        url=about["__url__"],
        # See https://pypi.org/classifiers/
        classifiers=[
            "Development Status :: 1 - Beta",
            "Programming Language :: Python :: 3 :: Only",
            "Programming Language :: Python :: 3.10",
        ],
        # Adding PROJECT_NAME as prefix to all packages to allow imports in the form: import project.package...
        packages=[PROJECT_NAME]
        + [
            f"{PROJECT_NAME}.{p}"
            for p in find_packages(PROJECT_NAME, exclude=["tests*"])
        ],
        package_dir={
            PROJECT_TITLE: PROJECT_NAME,
        },
        package_data={},
        install_requires=get_pipfile_requirements(),
        python_requires=">=3",
    )

