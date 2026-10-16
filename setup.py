from setuptools import setup, find_packages

setup(
    name="coronav",
    version="0.1.0",
    description="CoroNav: coronary guidewire-navigation environment for studying VLM operators' visual behaviour",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "numpy",
        "pillow",
        "scipy",
        "pyvista",
        "anthropic>=0.72.0",  # manuscript operator used v0.72.0 (pinned in docker/Dockerfile)
        # stEVE provides the intervention environment (requires SOFA — see docker/)
        "eve @ git+https://github.com/lkarstensen/stEVE.git@f909e7122d846a3c2fec91eedddaa0ba88b6391d",
    ],
    extras_require={
        "dev": ["pytest", "matplotlib"],
    },
)
