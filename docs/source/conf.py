# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
# Add the project root directory to the Python path so that autodoc can find the modules
sys.path.insert(0, os.path.abspath('../..'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'AgentConnect'
copyright = '2025, Akshat Joshi'
author = 'Akshat Joshi'

version = '0.1.0'
release = '0.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    # 'sphinx.ext.viewcode',  # Removed to disable source code viewing
    'sphinx.ext.napoleon',  # Support for NumPy and Google style docstrings
    'sphinx.ext.intersphinx',  # Link to other project's documentation
    'sphinx.ext.autosummary',  # Generate summary tables
    'sphinx_autodoc_typehints',  # Use type annotations for documentation
    'myst_parser',  # Support for Markdown
    'sphinx_design',  # Added from LangChain: Enhanced design components
    'sphinx_copybutton',  # Added from LangChain: Copy button for code blocks
]

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_attr_annotations = True

# Autodoc settings
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
    'special-members': '__init__',
}
autodoc_typehints = 'description'
autodoc_member_order = 'bysource'

# Fix for duplicate object descriptions
# This tells autodoc to not document the same object twice
autodoc_inherit_docstrings = True
autodoc_warningiserror = False

# Add this to prevent duplicate object descriptions
autodoc_default_flags = ['members', 'undoc-members', 'show-inheritance']

# Add this to handle duplicate class documentation
primary_domain = 'py'
add_module_names = False

# Intersphinx settings
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'langchain': ('https://api.python.langchain.com/en/latest/', None),
}

# MyST Markdown parser settings (from LangChain)
myst_enable_extensions = ['colon_fence']
source_suffix = ['.rst', '.md']

# Configure MyST to handle anchors in Markdown files
myst_heading_anchors = 3  # Generate anchors for h1, h2, and h3 headers

# Ignore specific warnings for specific files
nitpicky = False  # Don't be overly strict about warnings

# Exclude patterns for autodoc
# This helps with the duplicate object descriptions in the prompts module
exclude_patterns = [
    '_build',
    'Thumbs.db',
    '.DS_Store',
]

# Ignore specific modules for autodoc
# This helps with the duplicate object descriptions in the prompts module
autodoc_mock_imports = []

templates_path = ['_templates']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# Change to a dark theme
html_theme = 'sphinx_rtd_theme'  # We'll customize this with dark mode CSS

# Add custom CSS to enable dark mode for the Read the Docs theme
html_static_path = ['_static']
html_css_files = ['css/custom.css']

# Favicon and branding (can be customized later)
# html_favicon = '_static/favicon.png'

# Disable the generation of the index
html_use_index = False

# Don't copy source files to the output directory
html_copy_source = False

# Hide the "View page source" link
html_show_sourcelink = False

# -- Options for autosummary -------------------------------------------------
autosummary_generate = True  # Generate stub pages for autosummary directives

# -- GitHub context for "Edit on GitHub" links -------------------------------
html_context = {
    'display_github': True,
    'github_user': 'AKKI0511',  # Update with your GitHub username
    'github_repo': 'AgentConnect',  # Update with your repo name
    'github_version': 'main',  # Update with your default branch
    'conf_py_path': '/docs/source/',  # Path in the checkout to the docs root
}

# -- Copy button configuration -----------------------------------------------
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True
