from pathlib import Path
import markdown
import markmoji
from copy import deepcopy
import shutil
import os
import logging
import re

encoding = 'utf-8'
logging.getLogger().setLevel(logging.INFO)


def normalize(self, target):
    """
    Inverse of relative_to, honestly no idea why this isn't already in pathlib.Path
    """
    rel = target.relative_to(self)
    norm = Path()
    for p in rel.parents:
        if p != Path():
            norm /= ".."
    return norm
Path.normalize = normalize


# Define some useful paths
root = Path(__file__).parent
build = root / "docs"
source = root / "source"
# Setup markdown parser
md = markdown.Markdown(extensions=["extra", "admonition", "nl2br", markmoji.Markmoji()])
# Read in template
with open(str(root / "template.html"), "r", encoding=encoding) as f:
    template = f.read()
logging.info(f"Read {root / 'template.html'}.")


def indexFolder(file, levels=2):
    def _listMarkdownFiles(folder, level):
        # Stop once max level is reached
        if level >= levels:
            return ""
        # Work out indent level from level
        indent = ""
        for i in range(level):
            indent += "    "
        # String to store content
        contents = ""
        # Iterate through folders
        files = [f for f in folder.iterdir()]
        files.sort(key=lambda f: f.stem)
        for f in files:
            if f.is_dir() and not f.stem.startswith("_") and (f / "index.md").is_file():
                # If current f is an indexed folder, get its files recursively and add a heading
                contents += (
                    f"> {indent}* [{f.stem}]({f.relative_to(file.parent)})\n"
                    f"{_listMarkdownFiles(f, level=level+1)}"
                )
            elif f.is_dir() and not f.stem.startswith("_"):
                # If current f is a non indexed folder, get its files recursively but don't add a heading
                contents += (
                    f"{_listMarkdownFiles(f, level=level)}"
                )
        # Iterate through files
        for f in folder.glob("*.md"):
            if f.suffix == ".md" and f.stem != "index":
                # If f is a markdown file, add it
                contents += f"> {indent}* [{f.stem}]({f.relative_to(file.parent)})\n"
        
        return contents
    
    # Recursively build a contents
    return _listMarkdownFiles(file.parent, level=0)
    



def buildPage(file):
    """
    Build an html page in the build folder from a md file in the source folder.
    """
    def preprocess(content):
        """
        Transformations to apply to markdown content before compiling to HTML
        """
        # Style IPA strings
        def _ipa(match):
            ipa = match.group(1)
            return f"<a class=ipa href=http://ipa-reader.xyz/?text={ipa}&voice=Brian>{ipa}</a>"
        content = re.sub(r"^\/(.{1,})\/$", _ipa, content, flags=re.MULTILINE)
        # Replace refs to markdown files with refs to equivalent html files
        content = content.replace(".md)", ".html)")
        
        return content

    def postprocess(content):
        """
        Transformations to apply to HTML content after compiling from markdown
        """

        return content

    # Copy template
    page = deepcopy(template)

    # Create breadcrumbs for non-root files
    if file.parent == source:
        breadcrumbs = ""
    else:
        breadcrumbs = "<ul class=breadcrumbs>\n"
        parents = list(file.relative_to(source).parents)
        parents.reverse()
        for lvl in parents:
            # Don't make crumb for folder if this is its index file
            if file.stem == "index" and lvl.stem == file.parent.stem:
                continue
            # Different name for Home
            if lvl.stem == "":
                stem = "Home"
            else:
                stem = lvl.stem
            # Make a crumb for this level
            breadcrumbs += f"<li><a href={(source / lvl).parent.normalize(file).parent}>{stem}</a></li>\n"
        if file.stem == "index":
            stem = file.parent.stem
        else:
            stem = file.stem
        breadcrumbs += f"<li>{stem}</li>\n</ul>\n"
    page = page.replace("{{breadcrumbs}}", breadcrumbs)

    # Read markdown content
    with open(str(file), "r", encoding=encoding) as f:
        content_md = f.read()
    
    # For index files, create a contents box
    if file.stem == "index":
        contents = indexFolder(file, levels=2)
        content_md = f"{contents}\n{content_md}"
    
    # Get file stem
    if file.parent == source:
        stem = "Iuncterra"
    elif file.stem == "index":
        stem = file.parent.stem
    else:
        stem = file.stem

    # Update tab title
    tab = root.stem
    if file.parent != source:
        tab += ": " + stem
    page = page.replace("{{stem}}", tab)
    # Update page title (if there isn't one)
    if not content_md.startswith("# ") and file.parent != source:
        content_md = f"# {stem}\n{content_md}"

    # Transpile html content
    content_md = preprocess(content_md)
    content_html = md.convert(content_md)
    content_html = postprocess(content_html)
    # Insert content into page
    page = page.replace("{{content}}", content_html)
    
    
    # Normalize paths
    for key in ("root", "style", "utils"):
        norm = source.normalize(file)
        if key != "root":
            norm /= key
        page = page.replace("{{%s}}" % key, str(norm).replace("\\", "/"))
    # Remove underscore from assets links
    page = page.replace("_assets/", "assets/")
    # Where to write html file to?
    outpaths = []
    if file.stem == file.parent.stem:
        # If file acts as index, copy it to index.html
        outpaths.append(build / file.relative_to(source).parent / "index.html")
    outpaths.append(build / file.relative_to(source).parent / (file.stem + ".html"))
    # Create output files
    for outpath in outpaths:
        # Make sure directory exists
        if not outpath.parent.is_dir():
            os.makedirs(str(outpath.parent))
            logging.info(f"Created directory {outpath.parent}.")
        # Write html file
        with open(str(outpath), "w", encoding=encoding) as f:
            f.write(page)
        # Log
        logging.info(f"Written {outpath} from {file}.")


# Clear build folder
if build.is_dir():
    shutil.rmtree(build)
    logging.info(f"Deleted folder {build}")
os.mkdir(str(build))
logging.info(f"Created folder {build}")
# Copy style, assets and scripts over
for key in ("assets", "style", "utils"):
    # Copy source folder if there is one
    if (source / ("_" + key)).is_dir():
        shutil.copytree(
            source / ("_" + key),
            build / key
        )
        logging.info(f"Copied {source / key} to {build / key}.")
# Build every md file in source tree
for file in source.glob("**/*.md"):
    buildPage(file)
