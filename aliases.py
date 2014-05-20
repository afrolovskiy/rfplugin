import gcc


class AliasAnalyzer(gcc.GimplePass):
    def execute(self, fun):
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
        variables = [decl.name for decl in fun.local_decls if decl.name]
        variables.extend([v.decl.name for v in gcc.get_variables() if v.decl.name])
        pts = {v: set() for v in variables}

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

        # TODO: assign to any result of function analysis


ps = AliasAnalyzer(name='aliases')
ps.register_after('cfg')
