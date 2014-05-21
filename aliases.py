import json
import random

import gcc


class AliasAnalyzer(gcc.GimplePass):
    FAKE_RANGE = (0, 100000)

    def execute(self, fun):
        def init_shared_variable(decl):
          name = decl.name
          vtype = decl.type
          while isinstance(vtype, gcc.PointerType):
            # analyze each function independant from others so
            # add faked locations in order to emulate shared pointers
            # behaviour
            faked = 'fake{}'.format(random.randint(*self.FAKE_RANGE))
            pts[name] = set([faked])
            name, vtype = faked, vtype.type
          pts[name] = set()

        def eval_lhs(lhs):
          # x
          if isinstance(lhs, gcc.VarDecl):
            return set([lhs.name])

          # *x
          if isinstance(lhs, gcc.MemRef):
            return eval_rhs(lhs.operand)

          raise Exception('Unknown lhs type: {}'.format(type(lhs)))

        def eval_rhs(rhs):
          # x
          if isinstance(rhs, gcc.VarDecl):
            return pts[rhs.name]

          # &x
          if isinstance(rhs, gcc.AddrExpr):
            return set([rhs.operand.name])

          # *x
          if isinstance(rhs, gcc.MemRef):
            pt = set()
            for p in eval_rhs(rhs.operand):
              pt.update(pts[p])
            return pt

          raise Exception('Unknown rhs type: {}'.format(type(rhs)))

        # initialize points-to sets
        # initialize points-to sets
        # initialize points-to sets for local variables
        variables = [decl.name for decl in fun.local_decls if decl.name]
        pts = {v: set() for v in variables}
        # initialize points-to sets for global variables
        for variable in gcc.get_variables():
          init_shared_variable(variable.decl)
        # initialize points-to sets for function formal parameters
        for variable in fun.decl.arguments:
          init_shared_variable(variable)

        # iterate until fixed point reached
        changed = True;
        while changed:
          changed = False
          for block in fun.cfg.basic_blocks:
            for instr in block.gimple:
              # analyze only assignments operations
              if not isinstance(instr, gcc.GimpleAssign):
                continue

              # analyze only next types of expressions
              if instr.exprcode not in (gcc.VarDecl, gcc.AddrExpr, gcc.MemRef):
                continue

              # rhs must contain only 1 element
              if len(instr.rhs) > 1:
                continue

              lhs = eval_lhs(instr.lhs)
              rhs = eval_rhs(instr.rhs[0])

              for var in lhs:
                if not rhs.issubset(pts[var]):
                  pts[var].update(rhs)
                  changed = True

        # dump result of function analysis to file
        fname = 'output/{}.pts'.format(fun.decl.name)
        pts = {k: list(v) for k, v in pts.items()}
        with open(fname, 'w') as fo:
            fo.write(json.dumps(pts))


ps = AliasAnalyzer(name='aliases')
ps.register_after('cfg')
