# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
# Add the project root directory to the Python path so that autodoc can find the modules
sys.path.insert(0, os.path.abspath('../..'))

def setup(app):
    app.connect("autodoc-skip-member", skip_private_members)

def skip_private_members(app, what, name, obj, skip, options):
    if skip:
        return True
    if hasattr(obj, "__doc__") and obj.__doc__ and ":private:" in obj.__doc__:
        return True
    if name == "__init__" and obj.__objclass__ is object:
        # dont document default init
        return True
    return None

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'AgentConnect'
copyright = '2025, Akshat Joshi'
author = 'Akshat Joshi'

version = '0.3.0'
release = '0.3.0'

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
    'sphinx_markdown_builder',
    'sphinx_togglebutton',  # Add toggle button functionality
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

# Remove autodoc_default_flags which is deprecated
# Add this to handle duplicate class documentation
primary_domain = 'py'
# If false, no module index is generated.
add_module_names = False
python_use_unqualified_type_names = True  # Use unqualified names for type hints

# Remove common prefix from module names in the index
modindex_common_prefix = ['agentconnect.']

# Autosummary settings
autosummary_generate = True  # Generate stub pages with autosummary
autosummary_imported_members = False  # Don't document imported members

# For brevity in the navigation, don't show the full path of modules
# This setting affects how modules are displayed in the documentation
html_short_title = 'AgentConnect'
html_title = 'AgentConnect Documentation'

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

# Suppress specific warnings
suppress_warnings = [
    'docutils.nodes.title_reference',  # Suppress title reference warnings
    'app.add_directive',               # Suppress directive warnings
    'app.add_node',                    # Suppress node warnings
    'image.nonlocal_uri',              # Suppress nonlocal URI warnings
    'docutils.nodes.document',         # Suppress document warnings
    'docutils',                        # Suppress all docutils warnings (including title underlines)
]

# Additional warning handling settings
warning_is_error = False  # Don't treat warnings as errors
nitpick_ignore = []  # List of (type, target) tuples to ignore for nitpicky warnings

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

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# Use the PyData theme for a modern, responsive design with dark mode support
html_theme = 'pydata_sphinx_theme'

# Theme options
html_theme_options = {
    "logo": {
        "image_light": "_static/long_logo.png",
        "image_dark": "_static/long_logo.png",  # Consider a dark-theme optimized version if needed
        # "text": "AgentConnect",  # Remove text as it's in the image
    },
    "external_links": [
        {"name": "GitHub", "url": "https://github.com/AKKI0511/AgentConnect"},
    ],
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/AKKI0511/AgentConnect",
            "icon": "fab fa-github",
        },
    ],
    "use_edit_page_button": True,
    "show_toc_level": 2,
    "navbar_align": "left",
    "navbar_center": ["navbar-nav"],
    "navbar_end": ["navbar-icon-links", "theme-switcher"],
    # Make the navbar sticky
    "navbar_persistent": ["search-button"],
    # Make the primary sidebar collapsible and persistent
    "primary_sidebar_end": ["sidebar-ethical-ads"],
    "collapse_navigation": False,
    "navigation_depth": 4,
    # Show previous/next buttons
    "show_prev_next": True,
    # Increase contrast for better readability
    "pygment_light_style": "tango",
    "pygment_dark_style": "monokai",
    # Theme toggle settings
    "footer_start": ["copyright"],
    # Sidebar collapsing behavior
    "collapse_navigation": True,  # Allow sections to be collapsed
    "navigation_with_keys": True, # Allow keyboard navigation
    # Add sidebar collapse button by default
    "header_links_before_dropdown": 6,
}

# Add custom CSS to enable styling compatible with our custom.css
html_static_path = ['_static']
html_css_files = [
    'css/custom.css',
]

# # JavaScript files
# html_js_files = [
#     'js/custom.js',
# ]

# Template directory for custom templates
templates_path = ['_templates']

# Favicon and branding
html_favicon = '_static/final_logo.png'

# Enable the generation of the index
html_use_index = True

# Enable search index
html_search_index = True

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

# -- Toggle button configuration ----------------------------------------------
togglebutton_default_hide = False
togglebutton_hint = "Toggle details"

# -- HTML permalinks configuration -------------------------------------------
html_permalinks = True
html_permalinks_icon = "¶"
