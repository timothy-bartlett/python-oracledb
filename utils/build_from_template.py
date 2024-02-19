# -----------------------------------------------------------------------------
# Copyright (c) 2022, 2023, Oracle and/or its affiliates.
#
# This software is dual-licensed to you under the Universal Permissive License
# (UPL) 1.0 as shown at https://oss.oracle.com/licenses/upl and Apache License
# 2.0 as shown at http://www.apache.org/licenses/LICENSE-2.0. You may choose
# either license.
#
# If you elect to accept the software under the Apache License, Version 2.0,
# the following applies:
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# build_from_template.py
#
# Builds the parameter file from the template supplied on the command line.
# The generated file is written to the src/oracledb directory. The following
# template keys are recognized:
#
#   # {{ args_help_with_defaults }}
#       is replaced by the arguments help string with field defaults
#   # {{ async_args_help_with_defaults }}
#       is replaced by the arguments help string with field defaults (async)
#   # {{ args_help_without_defaults }}
#       is replaced by the arguments help string without field defaults
#   # {{ args_with_defaults }}
#       is replaced by the arguments with field defaults included
#   # {{ async_args_with_defaults }}
#       is replaced by the arguments with field defaults included (async)
#   # {{ generated_notice }}
#       is replaced by a notice that the file is generated and should not be
#       modified directly
#   # {{ params_constructor_args }}
#       is replaced by the constructor arguments for parameters
#   # {{ params_properties }}
#       is replaced by generated property getter and setter methods
#   # {{ params_repr }}
#       is replaced by a generated repr() for parameters
#   # {{ params_setter_args }}
#       is replaced by the arguments for the parameter set() method
#
# All of these could be accomplished by decorators, but doing so would
# eliminate the usefulness of static analyzers such as those used within Visual
# Studio Code.
# -----------------------------------------------------------------------------

import argparse
import configparser
import dataclasses
import os
import sys
import textwrap

TEXT_WIDTH = 79


@dataclasses.dataclass
class Field:
    name: str = ""
    typ: str = ""
    default: str = ""
    hidden: bool = False
    pool_only: bool = False
    description: str = ""
    decorator: str = None

    @property
    def async_description(self):
        return self.description.replace(
            "oracledb.Connection", "oracledb.AsyncConnection"
        )

    @property
    def async_typ(self):
        return self.typ.replace(
            "oracledb.Connection", "oracledb.AsyncConnection"
        )


# parse command line
parser = argparse.ArgumentParser(description="build module from template")
parser.add_argument("name", help="the name of the module to generate")
args = parser.parse_args()

# determine location of template and source and validate template
base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
target_dir = os.path.join(os.path.dirname(base_dir), "src", "oracledb")
template_name = os.path.join(base_dir, "templates", f"{args.name}.py")
config_name = os.path.join(base_dir, "fields.cfg")
target_name = os.path.join(target_dir, f"{args.name}.py")
if not os.path.exists(template_name):
    raise Exception(f"template {template_name} does not exist!")
if not os.path.exists(config_name):
    raise Exception(f"configuration {config_name} does not exist!")
code = open(template_name).read()
pool_only = "pool" in args.name

# acquire the fields from the configuration file
fields = []
config = configparser.ConfigParser()
config.read(config_name)
for section in config.sections():
    field = Field()
    field.name = section
    field.typ = config.get(section, "type")
    field.default = config.get(section, "default", fallback="None")
    field.hidden = config.getboolean(section, "hidden", fallback=False)
    field.pool_only = config.getboolean(section, "pool_only", fallback=False)
    field.description = config.get(section, "description", fallback="").strip()
    field.decorator = config.get(section, "decorator", fallback="")
    if not field.pool_only or pool_only:
        fields.append(field)


def replace_tag(tag, content_generator):
    """
    Replaces a template tag with content generated by a function. The content
    found before the tag is passed to the generator function.
    """
    global code
    search_value = "# {{ " + tag + " }}"
    while True:
        pos = code.find(search_value)
        if pos < 0:
            break
        prev_line_pos = code[:pos].rfind("\n")
        indent = code[prev_line_pos + 1 : pos]
        content = content_generator(indent)
        code = code[:pos] + content + code[pos + len(search_value) :]


def args_help_with_defaults_content(indent):
    """
    Generates the content for the args_help_with_defaults template tag.
    """
    raw_descriptions = [
        f"- {f.name}: {f.description} (default: {f.default})"
        for f in fields
        if f.description
    ]
    descriptions = [
        textwrap.fill(
            d,
            initial_indent=indent,
            subsequent_indent=indent + "  ",
            width=TEXT_WIDTH,
        )
        for d in raw_descriptions
    ]
    return "\n\n".join(descriptions).strip()


def args_help_without_defaults_content(indent):
    """
    Generates the content for the args_help_without_defaults template tag.
    """
    raw_descriptions = [
        f"- {f.name}: {f.description}" for f in fields if f.description
    ]
    descriptions = [
        textwrap.fill(
            d,
            initial_indent=indent,
            subsequent_indent=indent + "  ",
            width=TEXT_WIDTH,
        )
        for d in raw_descriptions
    ]
    return "\n\n".join(descriptions).strip()


def args_with_defaults_content(indent):
    """
    Generates the content for the args_with_defaults template tag.
    """
    args_joiner = "\n" + indent
    args = [f"{f.name}: {f.typ} = {f.default}," for f in fields]
    return args_joiner.join(args)


def async_args_help_with_defaults_content(indent):
    """
    Generates the content for the async_args_help_with_defaults template tag.
    """
    raw_descriptions = [
        f"- {f.name}: {f.async_description} (default: {f.default})"
        for f in fields
        if f.description
    ]
    descriptions = [
        textwrap.fill(
            d,
            initial_indent=indent,
            subsequent_indent=indent + "  ",
            width=TEXT_WIDTH,
        )
        for d in raw_descriptions
    ]
    return "\n\n".join(descriptions).strip()


def async_args_with_defaults_content(indent):
    """
    Generates the content for the async_args_with_defaults template tag.
    """
    args_joiner = "\n" + indent
    args = [f"{f.name}: {f.async_typ} = {f.default}," for f in fields]
    return args_joiner.join(args)


def generated_notice_content(indent):
    """
    Generates the content for the generated_notice template tag.
    """
    notice = """
            *** NOTICE *** This file is generated from a template and should
            not be modified directly. See build_from_template.py in the utils
            subdirectory for more information."""
    return textwrap.fill(
        textwrap.dedent(notice).strip(),
        subsequent_indent=indent,
        width=TEXT_WIDTH,
    )


def params_constructor_args_content(indent):
    """
    Generates the content for the params_constructor_args template tag.
    """
    args_joiner = f"\n{indent}"
    args = ["self,", "*,"] + [
        f"{f.name}: {f.typ} = {f.default}," for f in fields
    ]
    return args_joiner.join(args)


def params_properties_content(indent):
    """
    Generates the content for the params_properties template tag.
    """
    functions = []
    for field in sorted(fields, key=lambda f: f.name.upper()):
        if field.hidden:
            continue
        if field.pool_only != pool_only:
            continue
        description = f"{field.description[0].upper()}{field.description[1:]}."
        doc_string = textwrap.fill(
            description,
            initial_indent="    ",
            subsequent_indent="    ",
            width=TEXT_WIDTH - len(indent),
        )
        return_type = (
            f"Union[list, {field.typ}]" if field.decorator else field.typ
        )

        body_lines = (
            [
                "@property",
                f"@{field.decorator}" if field.decorator else "",
                f"def {field.name}(self) -> {return_type}:",
                '    """',
            ]
            + doc_string.splitlines()
            + ['    """', f"    return self._impl.{field.name}"]
        )
        joiner = "\n" + indent
        functions.append(joiner.join(s for s in body_lines if s))
    joiner = "\n\n" + indent
    return joiner.join(functions)


def params_repr_content(indent):
    """
    Generates the content for the params_repr template tag.
    """
    parts = [
        f'\n{indent}        + f"{field.name}={{self.{field.name}!r}}, "'
        for field in fields
        if not field.hidden
    ]
    parts[-1] = parts[-1][:-3] + '"'
    func_def = "def __repr__(self):"
    return (
        func_def
        + f"\n{indent}    return ("
        + f"\n{indent}        self.__class__.__qualname__"
        + f'\n{indent}        + "("'
        + "".join(parts)
        + f'\n{indent}        + ")"'
        + f"\n{indent}    )"
    )


def params_setter_args_content(indent):
    """
    Generates the content for the params_setter_args template tag.
    """
    args_joiner = f"\n{indent}"
    args = ["self,", "*,"] + [f"{f.name}: {f.typ} = None," for f in fields]
    return args_joiner.join(args)


# replace generated_notice template tag
replace_tag("args_help_with_defaults", args_help_with_defaults_content)
replace_tag(
    "async_args_help_with_defaults", async_args_help_with_defaults_content
)
replace_tag("args_help_without_defaults", args_help_without_defaults_content)
replace_tag("args_with_defaults", args_with_defaults_content)
replace_tag("async_args_with_defaults", async_args_with_defaults_content)
replace_tag("generated_notice", generated_notice_content)
replace_tag("params_constructor_args", params_constructor_args_content)
replace_tag("params_properties", params_properties_content)
replace_tag("params_repr", params_repr_content)
replace_tag("params_setter_args", params_setter_args_content)

# write the final code to the target location
open(target_name, "w").write(code)
