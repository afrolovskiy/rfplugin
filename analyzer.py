import hashlib
import random
import copy

import gcc


def count_repetitions(array, value):
    count = 0
    for element in array:
        if element == value:
            count = count + 1
    return count


class Type(object):
    def __init__(self, name):
        self.name = name

    def __dict__(self):
        return {
            'name': self.name,
        }

    def __repr__(self):
        return 'Type(name={!r})'.format(self.name)

    def __eq__(self, other):
        return self.__dict__() == other.__dict__()


class PointerType(Type):
    def __init__(self, type):
        super(PointerType, self).__init__(name='pointer')
        self.type = type

    def __dict__(self):
        return {
            'name': self.name,
            'type': self.type.__dict__(),
        }

    def __repr__(self):
        return 'PointerType(type={!r})'.format(self.type)

    def __eq__(self, other):
        return self.__dict__() == other.__dict__()


class Variable(object):
    def __init__(self, name, type, value=None):
        self.name = name
        self.type = type
        self.value = value

    def __dict__(self):
        return {
            'name': self.name,
            'type': self.type.__dict__(),
            'value': self.value.__dict__() if hasattr(self.value, 'to_dict') else self.value,
        }

    def __repr__(self):
        return 'Variable(name={!r}, type={!r}, value={!r}, shared={!r})'.format(
            self.name, self.type, self.value, self.shared
        )

    def __eq__(self, other):
        return self.__dict__() == other.__dict__()


class Address(object):
    def __init__(self, variable):
        self.variable = variable

    def __dict__(self):
        return {
            'address_of': self.variable.__dict__(),
        }

    def __repr__(self):
        return 'Address(variable={!r})'.format(self.variable)

    def __eq__(self, other):
        return self.__dict__() == other.__dict__()


class RelativeLockset(object):
    def __init__(self):
        self.acquired = set()
        self.released = set()

    def __dict__(self):
        return {
            'acquired': [l.__dict__() for l in self.acquired],
            'released': [l.__dict__() for l in self.released],
        }

    def __repr__(self):
        return 'RelativeLockset(acquired={!r}, released={!r})'.format(
            ','.join([repr(l) for l in self.acquired]),
            ','.join([repr(l) for l in self.released]),
        )


class Access(object):
    READ = 'read'
    WRITE = 'write'

    def __init__(self, value, lockset, kind):
        self.value = copy.deepcopy(value)
        self.lockset = copy.deepcopy(lockset)
        self.kind = kind


class Analyzer(gcc.GimplePass):
    K = 3

    def __init__(self, *args, **kwargs):
        super(Analyzer, self).__init__(*args, **kwargs)

    def execute(self, fun):
        print '==============={}==============='.format(fun.decl.name)
        self.print_info(fun)  # for debug

        pathes = self.build_pathes(fun)
        #self.print_pathes(pathes)  # for debug

        lock_summary = None
        access_summary = []

        for path in pathes:
            lockset, accesses = self.analyze_path(fun, path)
            if lock_summary is None:
                lock_summary = lockset
            lock_summary[0] = lock_summary[0].intersection(lockset[0])
            lock_summary[1] = lock_summary[1].union(lockset[1])
            access_summary.extend(accesses)

        print 'lock_summary:', lock_summary
        print 'access_summary:', access_summary

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
        lockset = [set(), set()]

        variables, shared = self.init_variables(fun)
        import ipdb; ipdb.set_trace()
        
        for block in path:
            for stat in block.gimple:
                print '+++++++++++++++++++++++++'
                print 'Instruction: {}'.format(str(stat))

                # add record to table accesses if needed
                self.analyze_accesses(stat, variables, shared, lockset, accesses)

                # analyze pointers
                #if isinstance(stat, gcc.GimpleAssign) and len(stat.rhs) == 1:
                #    lhs, rhs = stat.lhs, stat.rhs[0]
                #    self.analyze_aliases(lhs, rhs, aliases)

                #if isinstance(stat, gcc.GimpleCall):
                #    self.analyze_call(stat, shared, aliases, lockset, accesses)

                print 'lockset: {}'.format(lockset)
                print 'accesses: {}'.format(accesses)

        return lockset, accesses

    def init_variables(self, fun):
        def init_variable(name, vtype):
            if isinstance(vtype, gcc.PointerType):
                faked = '{}_location'.format(name)
                variable = init_variable(faked, vtype.type)
                return Variable(name=name, type=PointerType(type=variable.type), value=Address(variable))
            return Variable(name=name, type=Type(name=str(vtype)))

        variables, shared = {}, []

        # initialize global variables
        for var in gcc.get_variables():
            variables[str(var.decl)] = init_variable(str(var.decl), var.decl.type)
            shared.append(str(var.decl))

        # initialize formal parameters
        for decl in fun.decl.arguments:
            variables[str(decl)] = init_variable(str(decl), decl.type)
            shared.append(str(decl))

        # initialize local variables
        for decl in fun.local_decls:
            variables[str(decl)] = init_variable(str(decl), decl.type)

        return variables, shared

    def analyze_accesses(self, stat, variables, shared, lockset, accesses):
        if isinstance(stat, gcc.GimpleAssign):
            # analyze left side of assignment
            self.analyze_value(stat.lhs, variables, shared, lockset, accesses, 'write')
        
            # analyze right side of assign
            for rhs in stat.rhs:
                self.analyze_value(rhs, variables, shared, lockset, accesses, 'read')

        elif isinstance(stat, gcc.GimpleCall):
            if stat.lhs:
                # analyze lhs
                self.analyze_value(stat.lhs, variables, shared, lockset, accesses, 'write')

            # analyze function arguments
            for rhs in stat.args:
                self.analyze_value(rhs, variables, shared, lockset, accesses, 'read')

        elif isinstance(stat, gcc.GimpleReturn):
            if stat.retval:
                # analuze returned value
                self.analyze_value(stat.retval, variables, shared, lockset, accesses, 'read')

        elif isinstance(stat, gcc.GimpleLabel):
            # nothing to do
            pass

        elif (isinstance(stat, gcc.GimpleCond) and stat.exprcode in
                (gcc.EqExpr, gcc.NeExpr, gcc.LeExpr, gcc.LtExpr, gcc.GeExpr, gcc.GtExpr,)):
            # analyze left and right side of compare expression
            self.analyze_value(stat.lhs, variables, shared, lockset, accesses, 'read')
            self.analyze_value(stat.rhs, variables, shared, lockset, accesses, 'read')
        else:
            raise Exception('Unhandled statement: {}'.format(repr(stat)))

    def analyze_value(self, value, variables, shared, lockset, accesses, kind):
        if isinstance(value, (gcc.VarDecl, gcc.ParmDecl)):
            # p
            if str(value) in shared:
                accesses.append((variables[str(value)], copy.deepcopy(lockset), kind))
        elif isinstance(value, gcc.MemRef):
            # *p
            value = variables[str(value.operand)].value
            if value and isinstance(value, Address) and value.variable.name in shared:
                accesses.append((accessed, copy.deepcopy(lockset), kind))
        elif isinstance(value, (gcc.IntegerCst, gcc.AddrExpr, gcc.Constructor)):
            # nothing to do
            pass
        else:
            raise Exception('Unexpected value: {}'.format(repr(value)))

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

    def analyze_call(self, stat, shared, aliases, lockset, accesses):
        import ipdb; ipdb.set_trace()
        if stat.fndecl.name == 'pthread_mutex_lock':
            # analyze mutex lock
            arg = stat.args[0]
            if isinstance(arg, gcc.AddrExpr) and str(arg.operand) in shared:
                lockset[0].add(str(arg.operand))
                if str(arg.operand) in lockset[1]:
                    lockset[1].remove(str(arg.operand))
            else:
                
                pass
        elif stat.fndecl.name == 'pthread_mutex_unlock':
            # analyze mutex unlock
            pass
        else:
            # other functions analysis
            pass


ps = Analyzer(name='analyze')
ps.register_after('cfg')
