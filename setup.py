from setuptools import setup, find_packages

setup(
    name="coronav",
    version="0.1.0",
    description="CoroNav: open coronary VLM-operator navigation benchmark",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "numpy",
        "pillow",
        "scipy",
        "pyvista",
        "anthropic>=0.72.0",
        # stEVE provides the intervention environment (requires SOFA — see docker/)
        "eve @ git+https://github.com/lkarstensen/stEVE.git",
    ],
    extras_require={
        "dev": ["pytest", "matplotlib"],
    },
)
