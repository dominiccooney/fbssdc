#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Generates helpers from the ES6 IDL aimed to support a C++ decoder
# implementation.

import re

import encode
import model
import idl

class TypeVisitor(object):
  """Traverses a type hierarchy from a given root."""
  def __init__(self, resolver):
    self.resolver = resolver
    self.visited_types = set()

  def visit(self, ty: idl.Ty):
    if ty in self.visited_types:
      return
    self.visited_types.add(ty)

    if type(ty) is idl.TyInterface:
      self.visit_interface_type(ty)
      for attr in ty.attrs:
        self.visit(attr.resolved_ty)
    elif type(ty) is idl.Alt:
      self.visit_alt_type(ty)
      for subty in ty.tys:
        self.visit(subty)
    elif type(ty) is idl.TyEnum:
      self.visit_enum_type(ty)
    elif type(ty) is idl.TyPrimitive:
      self.visit_primitive_type(ty)
    elif type(ty) is idl.TyFrozenArray:
      self.visit_frozen_array_type(ty)
      self.visit(ty.element_ty)

  def visit_interface_type(self, ty):
    raise NotImplementedError()

  def visit_alt_type(self, ty):
    raise NotImplementedError()

  def visit_enum_type(self, ty):
    raise NotImplementedError()

  def visit_primitive_type(self, ty):
    raise NotImplementedError()

  def visit_frozen_array_type(self, ty):
    raise NotImplementedError()


class CppTypeMacroGenerator(TypeVisitor):
  def generate(self):
    self.interfaces = []
    self.alts = []
    self.enums = []
    self.primitives = []
    self.frozen_arrays = []
    self.model_ids = dict()
    self.next_model_id = 0
    self.visit(self.resolver.interfaces['Script'])

  def _cpp_name(self, ty):
    """Returns a tokenizable C++ identifier from the given type."""
    if type(ty) is idl.Alt:
      return 'Or'.join([ self._cpp_name(subty) for subty in ty.tys ])
    elif type(ty) is idl.TyFrozenArray:
      return f'FrozenArray_{self._cpp_name(ty.element_ty)}'
    elif type(ty) is idl.TyNone:
      return 'None'

    return ty.name

  def _get_insert_model_id(self, k):
    if k in self.model_ids:
      return self.model_ids[k]
    else:
      model_id = self.next_model_id
      self.model_ids[k] = model_id
      self.next_model_id += 1
      return model_id

  def visit_interface_type(self, ty):
    fields = []
    for attr in ty.attrs:
      model_id = self._get_insert_model_id((ty, attr.name))
      fields.append((attr.name, self._cpp_name(attr.resolved_ty), 'true' if attr.lazy else 'false', model_id))
    self.interfaces.append((self._cpp_name(ty), fields))

  def visit_alt_type(self, ty):
    self.alts.append((self._cpp_name(ty), [ self._cpp_name(subty) for subty in ty.tys ]))

  def visit_enum_type(self, ty):
    # TODO(acomminos): embed value for constant generation
    self.enums.append(self._cpp_name(ty))

  def visit_primitive_type(self, ty):
    self.primitives.append(self._cpp_name(ty))

  def visit_frozen_array_type(self, ty):
    model_id = self._get_insert_model_id((ty, 'list-length'))
    self.frozen_arrays.append((self._cpp_name(ty), self._cpp_name(ty.element_ty), model_id))

  def gen_all(self):
    return '\n'.join([
      self.gen_interfaces(),
      self.gen_alts(),
      self.gen_enums(),
      self.gen_primitives(),
      self.gen_frozen_arrays(),
      ])

  def gen_interfaces(self):
    def gen_fields(fields):
      return ', '.join([ f'T({name}, {ty_name}, {lazy}, {model_id})' for name, ty_name, lazy, model_id in fields ])

    interfaces = ' \\\n'.join([ f'  V({name}, {gen_fields(fields)})' for name, fields in self.interfaces ])

    return f'#define BINAST_INTERFACES(V,T) \\\n{interfaces}'

  def gen_alts(self):
    def gen_subtypes(tys):
      return ', '.join([ self._cpp_name(ty) for ty in tys ])

    alts = ' \\\n'.join([ f'  V({name}, T({", ".join(subtys)})' for name, subtys in self.alts ])

    return f'#define BINAST_ALTS(V,T) \\\n{alts}\n'

  def gen_enums(self):
    enums = ' \\\n'.join([ f'  V({name})' for name in self.enums ])
    return f'#define BINAST_ENUMS(V) \\\n{enums}\n'

  def gen_primitives(self):
    primitives = ' \\\n'.join([ f'  V({name})' for name in self.primitives ])
    return f'#define BINAST_PRIMITIVES(V) \\\n{primitives}\n'

  def gen_frozen_arrays(self):
    frozen_arrays = ' \\\n'.join([ f'  V({name}, {elem_name}, {model_id})' for name, elem_name, model_id in self.frozen_arrays ])
    return f'#define BINAST_FROZEN_ARRAYS(V) \\\n{frozen_arrays}\n'


SYMBOL_NAMES = {
  '+': 'PLUS',
  '-': 'MINUS',
  '=': 'EQUAL',
  '/': 'SLASH',
  '*': 'STAR',
  '<': 'LESS',
  '>': 'GREATER',
  '|': 'PIPE',
  '^': 'HAT',
  '&': 'AND',
  ',': 'COMMA',
  '!': 'BANG',
  '%': 'PCT',
  '~': 'TILDE',
}


class CppEnumTranslator(object):
  '''Given a Web IDL enum, generates a C++ enum with the same symbols.

  When serializing models, enumerations are partly ordered by the
  string values of the Web IDL enum members. C++ has no use for the
  string values, but does need the order, so the generated enum values
  are in this order.
  '''
  def __init__(self, types):
    self.types = types

  def gen(self):
    return '\n\n'.join(map(self.gen_enum, self.types.enums.values()))

  def gen_enum(self, ty):
    specials = frozenset(SYMBOL_NAMES.keys())
    def make_name(v: str):
      chs = frozenset(v)
      if chs - specials:
        name = re.sub('[- ]', '_', v).upper()
      else:
        name = '_'.join([SYMBOL_NAMES[ch] for ch in v])
      return name
    values = sorted(ty.values)
    members = ',\n  '.join(map(make_name, values))
    return f'enum class {ty.name} {{\n  {members}\n}};'


def main():
  resolver = idl.parse_es6_idl()
  generator = CppTypeMacroGenerator(resolver)
  generator.generate()
  print(generator.gen_all())

  enums = CppEnumTranslator(resolver)
  print(enums.gen())


if __name__ == '__main__':
  main()
