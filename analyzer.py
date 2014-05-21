import random
import copy

import gcc


def count_repetitions(array, value):
    count = 0
    for element in array:
        if element == value:
            count = count + 1
    return count


class Analyzer(gcc.GimplePass):
    K = 3

    def __init__(self, *args, **kwargs):
        super(Analyzer, self).__init__(*args, **kwargs)
        self.lock_summaries = {}

    def execute(self, fun):
        #self.print_info(fun)  # for debug

        pathes = self.build_pathes(fun)
        #self.print_pathes(pathes)  # for debug

        for path in pathes:
            lock_summary, accesses = self.analyze_path(fun, path)

    def build_pathes(self, fun):
        def walk(block, path):
            if count_repetitions(path, block) > Analyzer.K:
                return []

            path.append(block)

            if block.index == fun.cfg.exit.index:
                return [path]

            pathes = []
            for edge in block.succs:
                pathes.extend(walk(edge.dest, list(path)))

            return pathes

        return walk(fun.cfg.entry, [])

    def print_pathes(self, pathes):
        for path in pathes:
            print '[{}]'.format(','.join([str(b.index) for b in path]))

    def print_info(self, fun):
        print 'Function: {}'.format(fun.decl.name)
        for bb in fun.cfg.basic_blocks:
            print 'Basic block: {}'.format(str(bb))
            for ss in bb.gimple:
                print 'Instrruction: {}'.format(str(ss))
                print 'Type: {}'.format(repr(ss))

    def analyze_path(self, fun, path):
        print 'analyzed path: [{}]'.format(','.join([str(b.index) for b in path]))

        accesses = []
        lockset = tuple([set(), set()])

        aliases = {}
        shared = []
        
        def init_variable(decl):
            name, vtype = str(decl), decl.type
            while isinstance(vtype, gcc.PointerType):
                # analyze each function independant from others so
                # add faked locations in order to emulate shared pointers
                # behaviour
                faked = 'ptr_{}'.format(name)
                aliases[name] = faked
                name, vtype = faked, vtype.type

        for variable in gcc.get_variables():
            init_variable(variable.decl)
            shared.append(str(variable.decl))

        for decl in fun.local_decls:
            init_variable(decl)

        for decl in fun.decl.arguments:
            init_variable(decl)
            shared.append(str(decl))

        for block in path:
            for stat in block.gimple:
                print '+++++++++++++++++++++++++'
                print 'Instruction: {}'.format(str(stat))

                # add record to table accesses if needed
                self.analyze_statement(stat, shared, aliases, lockset, accesses)

                # analyze pointers
                if isinstance(stat, gcc.GimpleAssign) and len(stat.rhs) == 1:
                    lhs, rhs = stat.lhs, stat.rhs[0]
                    self.analyze_aliases(lhs, rhs, aliases)

                print 'pointers: {}'.format(aliases)
                print 'accesses: {}'.format(accesses)

        return None, None  # stub

    def analyze_statement(self, stat, shared, aliases, lockset, accesses):
        if isinstance(stat, gcc.GimpleAssign):
            # analyze left side of assignment
            self.analyze_value(stat.lhs, shared, aliases, lockset, accesses, 'write')
        
            # analyze right side of assign
            for rhs in stat.rhs:
                self.analyze_value(rhs, shared, aliases, lockset, accesses, 'read')

        elif isinstance(stat, gcc.GimpleCall):
            if stat.lhs:
                # analyze lhs
                self.analyze_value(stat.lhs, shared, aliases, lockset, accesses, 'write')

            for rhs in stat.args:
                self.analyze_value(rhs, shared, aliases, lockset, accesses, 'read')

        elif isinstance(stat, gcc.GimpleReturn):
            if stat.retval:
                self.analyze_value(stat.retval, shared, aliases, lockset, accesses, 'read')

        elif isinstance(stat, gcc.GimpleLabel):
            # nothing to do
            pass

        elif isinstance(stat, gcc.GimpleCond):
            if stat.exprcode in (gcc.EqExpr, gcc.NeExpr, gcc.LeExpr, gcc.LtExpr, gcc.GeExpr, gcc.GtExpr,):
                self.analyze_value(stat.lhs, shared, aliases, lockset, accesses, 'read')
                self.analyze_value(stat.rhs, shared, aliases, lockset, accesses, 'read')
            else:
                raise Exception("Unhandled instruction: {}".format(repr(stat)))
        else:
            raise Exception("Unhandled instruction: {}".format(repr(stat)))

    def analyze_value(self, value, shared, aliases, lockset, accesses, kind):
        if isinstance(value, (gcc.VarDecl, gcc.ParmDecl)):
            # p = ...
            if str(value) in shared:
                #  => (p, L, write)
                accesses.append((str(value), copy.deepcopy(lockset), kind))
        elif isinstance(value, gcc.MemRef):
            # *p = ...
            if str(value.operand) in shared:
                # => (p, L, write)
                accesses.append((str(value.operand), copy.deepcopy(lockset), kind))
            else:
                # find shared variable which can points to same location with "p"
                points_to = aliases.get(str(value.operand))
                if points_to:
                    for k, v in aliases.items():
                        if v == points_to and k in shared:
                            accesses.append(('*{}'.format(k), copy.deepcopy(lockset), kind))
        elif isinstance(value, (gcc.IntegerCst, gcc.AddrExpr, gcc.Constructor)):
            # nothing to do
            pass
        else:
            raise Exception("Unexpected value: {}".format(repr(value)))

    def analyze_aliases(self, lhs, rhs, aliases):
        if isinstance(lhs, gcc.MemRef):  # *p
            if isinstance(rhs, gcc.AddrExpr):
                # *p = &q
                #        q
                #        ^   
                #        |
                # p ---> r
                points_to = aliases.get(str(lhs.operand))
                if points_to:
                    aliases[points_to] = str(rhs.operand)
            elif isinstance(rhs, gcc.MemRef):
                # *p = *q
                # q ---> b ---> c
                #               ^
                #               |
                #        p ---> a
                ppoints_to = aliases.get(str(lhs.operand))
                qpoints_to = aliases.get(str(rhs.operand))
                if ppoints_to and qpoints_to and aliases.get(qpoints_to):
                    aliases[ppoints_to] = aliases[qpoints_to]
            elif isinstance(rhs, (gcc.VarDecl, gcc.ParmDecl)):
                # *p = q
                # q ---> b
                #        ^
                #        |
                # p ---> r
                ppoints_to = aliases.get(str(lhs.operand))
                qpoints_to = aliases.get(str(rhs))
                if ppoints_to and qpoints_to:
                    aliases[ppoints_to] = qpoints_to
            elif isinstance(rhs, (gcc.IntegerCst, gcc.Constructor)):
                # nothing to do
                pass
            else:
                raise Exception("Unexpected rhs: {}".format(repr(rhs)))

        elif isinstance(lhs, (gcc.VarDecl, gcc.ParmDecl)):  # p
            if isinstance(rhs, gcc.AddrExpr):
                # p = &q
                # p ---> q
                aliases[str(lhs)] = str(rhs.operand)
            elif isinstance(rhs, gcc.MemRef):
                # p = *q
                # q ---> a ---> b
                #               ^
                #               |
                #               p
                points_to = aliases.get(str(rhs.operand))
                if points_to and aliases.get(points_to):
                    aliases[str(lhs)] = aliases[points_to]
            elif isinstance(rhs, (gcc.VarDecl, gcc.ParmDecl)):
                # p = q
                # q ---> a
                #        ^
                #        |
                #        p
                points_to = aliases.get(str(rhs))
                if points_to:
                    aliases[str(lhs)] = points_to
            elif isinstance(rhs, (gcc.IntegerCst, gcc.Constructor)):
                # nothing to do
                pass
            else:
                raise Exception("Unexpected rhs: {}".format(repr(rhs)))
        else:
            raise Exception("Unexpected lhs: {}".format(repr(lhs)))


ps = Analyzer(name='analyze')
ps.register_after('cfg')
