from pprint import pprint
import random
import copy

import gcc


def count_repetitions(array, value):
    count = 0
    for element in array:
        if element == value:
            count = count + 1
    return count


class RelativeLockset(object):
    def __init__(self, acquired=None, released=None):
        self.acquired = acquired or set()
        self.released = released or set()

    def __hash__(self):
        acquired = sum([hash(l) for l in self.acquired])
        released = sum([hash(l) for l in self.released])
        return acquired + 5 * released

    def __eq__(self, other):
        return hash(self) == self(other)

    def to_dict(self):
        return {
            'acquired': [l.to_dict() for l in self.acquired],
            'released': [l.to_dict() for l in self.released],
        }

    def acquire(self, lock):
        if lock in self.released:
            self.released.remove(lock)
        self.acquired.add(lock)

    def release(self, lock):
        if lock in self.acquired:
            self.acquired.remove(lock)
        else:
            self.released.add(lock)

    def update(self, lockset):
        self.acquired = self.acquired.intersection(lockset.acquired)
        self.released = self.released.union(lockset.released)


class GuardedAccess(object):
    READ = 'read'
    WRITE = 'write'

    def __init__(self, access, lockset, kind, file=None, line=None):
        self.access = access
        self.lockset = lockset
        self.kind = kind
        self.file = file
        self.line = line

    def __hash__(self):
        access = hash(self.access)
        lockset = hash(self.lockset)
        kind = hash(self.kind)
        return access + 2 * lockset + 3 * kind + hash(self.line) + hash(self.file)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def to_dict(self):
        return {
            'access': self.access.to_dict(),
            'lockset': self.lockset.to_dict(),
            'kind': self.kind,
            'file': self.file,
            'line': self.line,
        }


class GuardedAccessTable(object):
    def __init__(self, accesses=None):
        self.accesses = accesses or set()

    def to_dict(self):
        return [ga.to_dict() for ga in self.accesses]

    def add(self, access):
        if access not in self.accesses:
            self.accesses.add(access)

    def update(self, table):
        self.accesses.update(table.accesses)


class Type(object):
    def __init__(self, name):
        self.name = name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def to_dict(self):
        return {
            'name': self.name,
        }


class PointerType(Type):
    def __init__(self, type):
        super(PointerType, self).__init__(name='pointer')
        self.type = type

    def __hash__(self):
        return hash(self.name) + 3 * hash(self.type)

    def to_dict(self):
        return {
            'name': self.name,
            'type': self.type.to_dict(),
        }


class Location(object):
    VISIBILITY_GLOBAL = 'global'
    VISIBILITY_LOCAL = 'local'
    VISIBILITY_FORMAL = 'formal'

    STATUS_COMMON = 'common'
    STATUS_FAKE = 'fake'

    def __init__(self, name, type, visibility, status, value=None):
        self.name = name
        self.type = type
        self.visibility = visibility
        self.status = status
        self.value = value

    def __hash__(self):
        return (hash(self.name) + 2 * hash(self.type) + 3 * hash(self.visibility) +
                4 * hash(self.status))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def to_dict(self, with_value=True):
        res = {
            'name': self.name,
            'type': self.type.to_dict(),
            'visibility': self.visibility,
            'status': self.status,
        }
        if with_value:
            res['value'] = self.value.to_dict() if self.value else None
        return res

    def is_shared(self):
        return self.visibility in (self.VISIBILITY_GLOBAL, self.VISIBILITY_FORMAL)

    def is_formal(self):
        return self.visibility == self.VISIBILITY_FORMAL

    def is_fake(self):
        return self.status == self.STATUS_FAKE


class Address(object):
    def __init__(self, location):
        self.location = location

    def __hash__(self):
        return hash(self.location)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def to_dict(self):
        return {
            'address_of': self.location.to_dict()
        }


class Value(object):
    ID_RANGE = (0, 10000)

    def __init__(self):
        self.id = random.randint(*self.ID_RANGE)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def to_dict(self):
        return {
            'id': self.id,
        }


class RaceFinder(gcc.IpaPass):
    FAKE_RANGE = (0, 10000)
    MAX_LEVEL = 4

    def __init__(self, *args, **kwargs):
        super(RaceFinder, self).__init__(*args, **kwargs)
        self.summaries = {}
        self.global_variables = {}

    def execute(self, *args, **kwargs):
        self.global_variables = self.init_global_variables()
        for node in gcc.get_callgraph_nodes():
            if not self.is_analyzed(node):
                self.analyze_node(node)

    def init_global_variables(self):
        global_variables = {}
        for variable in gcc.get_variables():
            name, type = variable.decl.name, variable.decl.type
            global_variables[name] = self.init_variable(
                name, type, visibility=Location.VISIBILITY_GLOBAL)
        return global_variables

    def init_variable(self, name, type, visibility=None, status=None):
        visibility = visibility or Location.VISIBILITY_LOCAL
        status = status or Location.STATUS_COMMON

        if isinstance(type, gcc.PointerType):
            faked_name = '{}_fake_{}'.format(name, random.randint(*self.FAKE_RANGE))
            faked_location = self.init_variable(
               faked_name, type.type, visibility=visibility, status=Location.STATUS_FAKE)
            return Location(
                name=name,
                visibility=visibility,
                status=status,
                type=PointerType(type=faked_location.type),
                value=Address(faked_location)
            )

        return Location(
            name=name,
            type=Type(name=str(type)),
            visibility=visibility,
            status=status,
            value = Value()
        )

    def is_analyzed(self, node):
       return node.decl.name in self.summaries

    def get_node_by_name(self, name):
        # Returns node if exists, otherwise - None
        for node in gcc.get_callgraph_nodes():
            if node.decl.name == name:
                return node
        return None

    def analyze_node(self, node):
        #import ipdb; ipdb.set_trace()

        fun = node.decl.function
        print '==========================================='
        print 'Analyzed: {}'.format(node.decl.name)
        #self.print_info(fun)
        #print '------------------------------------------'

        variables = self.init_variables(fun)

        lockset_summary, access_summary = None, None

        pathes = self.build_pathes(fun)
        for path in pathes:
            lockset, access_table = self.analyze_path(fun, path, copy.deepcopy(variables))

            if lockset_summary is None:
                lockset_summary = lockset
            else:
                lockset_summary.update(lockset)

            if access_summary is None:
                access_summary = access_table
            else:
                access_summary.update(access_table)

        #print 'variables:'
        #for k, v in variables.items():
        #    pprint(v.to_dict())
        #print '----------'
        print 'lockset'
        pprint(lockset_summary.to_dict())
        print '---------'
        print 'accesses:'
        pprint(access_summary.to_dict())

        self.summaries[fun.decl.name] = {
            'lockset': lockset_summary,
            'accesses': access_summary,
            'formals': [variables[str(arg)] for arg in fun.decl.arguments],
        }

        #import ipdb; ipdb.set_trace()

    def print_info(self, fun):
        print 'Function: {}'.format(fun.decl.name)
        for bb in fun.cfg.basic_blocks:
            print 'Basic block: {}'.format(str(bb))
            for ss in bb.gimple:
                print 'Instrruction: {}'.format(str(ss))
                print 'Type: {}'.format(repr(ss))

    def build_pathes(self, fun):
        def walk(block, path):
            if count_repetitions(path, block) > RaceFinder.MAX_LEVEL:
                return []

            path.append(block)

            if block.index == fun.cfg.exit.index:
                return [path]

            pathes = []
            for edge in block.succs:
                pathes.extend(walk(edge.dest, list(path)))

            return pathes

        return walk(fun.cfg.entry, [])

    def analyze_path(self, fun, path, variables):
        lockset = RelativeLockset()
        access_table = GuardedAccessTable()

        for block in path:
            for stat in block.gimple:
                #print 'Instruction: {}'.format(str(stat))
                #print 'Type: {}'.format(repr(stat))
                self.analyze_statement(stat, variables, lockset, access_table)
                #print access_table.to_dict()
                #print lockset.to_dict()
                #print '+++++++++++++++++++++++++++++++'

        return lockset, access_table

    def init_variables(self, fun):
        variables = copy.deepcopy(self.global_variables)
        variables.update(self.init_formal_variables(fun))
        variables.update(self.init_local_variables(fun))
        return variables

    def init_formal_variables(self, fun):
        formal_parameters = {}
        for decl in fun.decl.arguments:
            name, type = str(decl), decl.type 
            formal_parameters[name] = self.init_variable(
                name, type, visibility=Location.VISIBILITY_FORMAL)
        return formal_parameters

    def init_local_variables(self, fun):
        local_variables = {}
        for decl in fun.local_decls:
            name, type = str(decl), decl.type
            local_variables[name] = self.init_variable(
                name, type, visibility=Location.VISIBILITY_LOCAL)
        return local_variables

    def analyze_statement(self, stat, variables, lockset, access_table):
        self.analyze_access(stat, variables, lockset, access_table)

        if isinstance(stat, gcc.GimpleAssign) and len(stat.rhs) == 1:
            lhs, rhs = stat.lhs, stat.rhs[0]
            self.analyze_aliases(lhs, rhs, variables)

        if isinstance(stat, gcc.GimpleCall):
            self.analyze_call(stat, variables, lockset)        

    def analyze_access(self, stat, variables, lockset, access_table):
        if isinstance(stat, gcc.GimpleAssign):
            # analyze left side of assignment
            self.analyze_value(stat.lhs, stat, variables, lockset, access_table, GuardedAccess.WRITE)

            # analyze right side of assign
            for rhs in stat.rhs:
                self.analyze_value(rhs, stat, variables, lockset, access_table, GuardedAccess.READ)

        elif isinstance(stat, gcc.GimpleCall):
            if stat.lhs:
                # analyze lhs
                self.analyze_value(stat.lhs, stat, variables, lockset, access_table, GuardedAccess.WRITE)

            # analyze function arguments
            for rhs in stat.args:
                self.analyze_value(rhs, stat, variables, lockset, access_table, GuardedAccess.READ)

        elif isinstance(stat, gcc.GimpleReturn):
            if stat.retval:
                # analuze returned value
                self.analyze_value(stat.retval, stat, variables, lockset, access_table, GuardedAccess.READ)

        elif isinstance(stat, gcc.GimpleLabel):
            # nothing to do
            pass

        elif (isinstance(stat, gcc.GimpleCond) and stat.exprcode in
                (gcc.EqExpr, gcc.NeExpr, gcc.LeExpr, gcc.LtExpr, gcc.GeExpr, gcc.GtExpr,)):
            # analyze left and right side of compare expression
            self.analyze_value(stat.lhs, stat, variables, lockset, access_table, GuardedAccess.READ)
            self.analyze_value(stat.rhs, stat, variables, lockset, access_table, GuardedAccess.READ)
        else:
            raise Exception('Unhandled statement: {}'.format(repr(stat)))

    def analyze_value(self, value, stat, variables, lockset, access_table, kind):
        #print 'Accessed value: {} with {}'.format(str(value), repr(value))
        if isinstance(value, gcc.SsaName):
            self.analyze_value(value.var, stat, variables, lockset, access_table, kind)
        elif isinstance(value, (gcc.VarDecl, gcc.ParmDecl)):
            # p
            location = variables[str(value)]
            if location.is_shared():
                access_table.add(GuardedAccess(
                    copy.deepcopy(location), copy.deepcopy(lockset), kind, stat.loc.file, stat.loc.line))
        elif isinstance(value, gcc.MemRef):
            # *p
            # harcoded
            name = str(value.operand.var) if isinstance(value.operand, gcc.SsaName) else str(value.operand)

            location = variables[name]
            if location.is_shared():
                access_table.add(GuardedAccess(
                    copy.deepcopy(location), copy.deepcopy(lockset), GuardedAccess.READ, stat.loc.file, stat.loc.line))

            accessed = location.value.location
            if accessed.is_shared():
                access_table.add(GuardedAccess(
                    copy.deepcopy(accessed), copy.deepcopy(lockset), kind, stat.loc.file, stat.loc.line))
        elif value is None or isinstance(value, (gcc.IntegerCst, gcc.AddrExpr, gcc.Constructor)):
            # do nothing
            pass
        else:
            raise Exception('Unexpected value: {}'.format(repr(value)))

    def analyze_aliases(self, lhs, rhs, variables):
        if isinstance(lhs, gcc.MemRef):  # *p
            # hardcoded
            lname = str(lhs.operand.var) if isinstance(lhs.operand, gcc.SsaName) else str(lhs.operand)

            if isinstance(rhs, gcc.AddrExpr):
                # *p = &q
                #        q
                #        ^   
                #        |
                # p ---> r
                r = variables[lname].value.location
                # hardcoded
                rname = str(rhs.operand.var) if isinstance(rhs.operand, gcc.SsaName) else str(rhs.operand)
                q = variables[rname]
                r.value = Address(q)
            elif isinstance(rhs, gcc.MemRef):
                # *p = *q
                # q ---> b ---> c
                #               ^
                #               |
                #        p ---> a
                a = variables[lname].value.location
                # hardcoded
                rname = str(rhs.operand.var) if isinstance(rhs.operand, gcc.SsaName) else str(rhs.operand)
                b = variables[rname].value.location
                a.value = b.value
            elif isinstance(rhs, (gcc.VarDecl, gcc.ParmDecl, gcc.SsaName)):
                # *p = q
                # q ---> b
                #        ^
                #        |
                # p ---> r
                r = variables[lname].value.location
                # hardcoded
                rname = str(rhs.var) if isinstance(rhs, gcc.SsaName) else str(rhs)
                q = variables[rname]
                r.value = q.value
            elif isinstance(rhs, (gcc.IntegerCst, gcc.Constructor)):
                # do nothing
                pass
            else:
                raise Exception("Unexpected rhs: {}".format(repr(rhs)))

        elif isinstance(lhs, (gcc.VarDecl, gcc.ParmDecl, gcc.SsaName)):  # p
            # hardcoded
            lname = str(lhs.var) if isinstance(lhs, gcc.SsaName) else str(lhs)
            if isinstance(rhs, gcc.AddrExpr):
                # p = &q
                # p ---> q
                # hardcoded
                rname = str(rhs.operand.var) if isinstance(rhs.operand, gcc.SsaName) else str(rhs.operand)
                p = variables[lname]
                q = variables[rname]
                p.value = Address(q)
            elif isinstance(rhs, gcc.MemRef):
                # p = *q
                # q ---> a ---> b
                #               ^
                #               |
                #               p
                # hardcoded
                rname = str(rhs.operand.var) if isinstance(rhs.operand, gcc.SsaName) else str(rhs.operand)
                p = variables[lname]
                q = variables[rname]
                a = q.value.location
                p.value = a.value
            elif isinstance(rhs, (gcc.SsaName, gcc.VarDecl, gcc.ParmDecl)):
                # p = q
                # q ---> a
                #        ^
                #        |
                #        p
                # hardcoded
                rname = str(rhs.var) if isinstance(rhs, gcc.SsaName) else str(rhs)
                p = variables[lname]
                q = variables[rname]
                p.value = q.value
            elif isinstance(rhs, (gcc.IntegerCst, gcc.Constructor)):
                # nothing to do
                pass
            else:
                raise Exception("Unexpected rhs: {}".format(repr(rhs)))
        else:
            raise Exception("Unexpected lhs: {}".format(repr(lhs)))

    def analyze_call(self, stat, variables, lockset):
        fname = str(stat.fndecl)
        if fname == 'pthread_mutex_lock':
            arg = stat.args[0]
            if isinstance(arg, gcc.AddrExpr):
                name = str(arg.operand.var) if isinstance(arg.operand, gcc.SsaName) else str(arg.operand)
                location = variables[name]
                lockset.acquire(Address(location))
            elif isinstance(arg, (gcc.SsaName, gcc.VarDecl, gcc.ParmDecl)):
                name = str(arg.var) if isinstance(arg, gcc.SsaName) else str(arg)
                location = variables[name]
                lockset.acquire(location.value)
            else:
                raise Exception('Unexpexted argument of pthread_mutex_lock')
        
        elif fname == 'pthread_mutex_unlock':
            arg = stat.args[0]
            if isinstance(arg, gcc.AddrExpr):
                name = str(arg.operand.var) if isinstance(arg.operand, gcc.SsaName) else str(arg.operand)
                location = variables[name]
                lockset.release(Address(location))
            elif isinstance(arg, (gcc.SsaName, gcc.VarDecl, gcc.ParmDecl)):
                name = str(arg.var) if isinstance(arg, gcc.SsaName) else str(arg)
                location = variables[name]
                lockset.release(location.value)
            else:
                raise Exception('Unexpexted argument of pthread_mutex_unlock')

        else:
            summary = self.summaries.get(fname)
            if summary is None:
                node = self.get_node_by_name(fname)
                if node is None:
                    # pass call of external function
                    return
                self.analyze_node(node)
                summary = self.summaries[fname]
            summary = self.rebindSummary(summary, stat, variables)
            import ipdb; ipdb.set_trace()

    def rebindSummary(self, summary, stat, variables):
        summary = copy.deepcopy(summary)

        # rebind guarded access table
        for ga in summary['accesses'].accesses:
            if ga.access.is_formal():
                # rebind accessed location
                ga.access = copy.deepcopy(self.find_rebinding_location(ga.access, stat.args, summary['formals'], variables))

            # rebind relative lockset
            ga.lockset = self.rebind_lockset(ga.lockset, stat.args, summary['formals'], variables)

        # rebind function relative lockset summary
        summary['lockset'] = self.rebind_lockset(summary['lockset'], stat.args, summary['formals'], variables)

        return summary

    def find_rebinding_location(self, location, args, formals, variables):
        idx, level = self.find_parent(location, formals)
        if idx is None or level is None:
            import ipdb; ipdb.set_trace()
            raise Exception('Critical error')

        arg = args[idx]
        vname = str(arg.var) if isinstance(arg, gcc.SsaName) else str(arg)
        new_location = variables[vname]
        for idx in range(level):
            new_location = new_location.value.location

        return new_location


    def find_parent(self, location, formals):
        for idx in range(len(formals)):
            formal, level = formals[idx], 0

            while True:
                if formal == location:
                    return idx, level

                formal = formal.value.location

                if isinstance(formal, Value):
                    break

                level = level + 1

        return None, None

    def rebind_lockset(self, lockset, args, formals, variables):
        new_lockset = RelativeLockset()

        for acquired in lockset.acquired:
            if acquired.is_formal():
                acquired = self.find_rebinding_location(acquired, args, formals, variables)
            new_lockset.acquired.add(copy.deepcopy(acquired))

        for released in lockset.released:
            if released.is_formal():
                released = self.find_rebinding_location(released, stat.args, summary['formals'], variables)
            new_lockset.released.add(copy.deepcopy(released))

        return new_lockset


ps = RaceFinder(name='race-finder')
ps.register_after('whole-program')

