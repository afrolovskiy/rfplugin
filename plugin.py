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


class GuardedAccess(object):
    KIND_READ = 'read'
    KIND_WRITE = 'write'

    def __init__(self, access, lockset, kind):
        self.access = access
        self.lockset = lockset
        self.kind = kind

    def __hash__(self):
        access = hash(self.access)
        lockset = hash(self.lockset)
        kind = hash(kind)
        return access + 2 * lockset + 3 * kind

    def __eq__(self, other):
        return hash(self) == hash(other)

    def to_dict(self):
        return {
            'access': self.access.to_dict(),
            'lockset': self.lockset.to_dict(),
            'kind': self.kind,
        }


class GuardedAccessTable(object):
    def __init__(self, accesses=None):
        self.accesses = accesses or set()

    def to_dict(self):
        return [ga.to_dict() for ga in self.accesses]

    def add(self, access):
        if access not in self.accesses:
            self.accesses.add(access)


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
        for node in gcc.get_callgraph_node():
            if node.decl.name == name:
                return node
        return None

    def analyze_node(self, node):
        fun = node.decl.function
        pathes = self.build_pathes(fun)
        variables = self.init_variables(fun)
        for path in pathes:
            self.analyze_path(fun, path, copy.deepcopy(variables))

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
                print 'Instruction: {}'.format(str(stat))
                self.analyze_statement(stat, variables, lockset, access_table)
                print access_table.to_dict()

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
        # TODO

    def analyze_access(self, stat, variables, lockset, access_table):
        if isinstance(stat, gcc.GimpleAssign):
            # analyze left side of assignment
            self.analyze_value(stat.lhs, variables, lockset, access_table, GuardedAccess.WRITE)

            # analyze right side of assign
            for rhs in stat.rhs:
                self.analyze_value(rhs, variables, lockset, access_table, GuardedAccess.READ)

        elif isinstance(stat, gcc.GimpleCall):
            if stat.lhs:
                # analyze lhs
                self.analyze_value(stat.lhs, variables, lockset, access_table, GuardedAccess.WRITE)

            # analyze function arguments
            for rhs in stat.args:
                self.analyze_value(rhs, variables, lockset, access_table, GuardedAccess.READ)

        elif isinstance(stat, gcc.GimpleReturn):
            if stat.retval:
                # analuze returned value
                self.analyze_value(stat.retval, variables, lockset, access_table, GuardedAccess.READ)

        elif isinstance(stat, gcc.GimpleLabel):
            # nothing to do
            pass

        elif (isinstance(stat, gcc.GimpleCond) and stat.exprcode in
                (gcc.EqExpr, gcc.NeExpr, gcc.LeExpr, gcc.LtExpr, gcc.GeExpr, gcc.GtExpr,)):
            # analyze left and right side of compare expression
            self.analyze_value(stat.lhs, variables, lockset, access_table, GuardedAccess.READ)
            self.analyze_value(stat.rhs, variables, lockset, access_table, GuardedAccess.READ)
        else:
            raise Exception('Unhandled statement: {}'.format(repr(stat)))

    def analyze_value(self, value, variables, lockset, access_table, kind):
        if isinstance(value, (gcc.VarDecl, gcc.ParmDecl)):
            # p
            location = variables[str(value)]
            if location.is_shared():
                access_table.add(GuardedAccess(
                    copy.deepcopy(location), copy.deepcopy(lockset), kind))
        elif isinstance(value, gcc.MemRef):
            # *p
            location = variables[str(value.operand)]
            if location.is_shared():
                access_table.add(GuardedAccess(
                    copy.deepcopy(location), copy.deepcopy(lockset), GuardedAccess.READ))

            accessed = location.value.location
            if accessed.is_shared():
                access_table.add(GuardedAccess(
                    copy.deepcopy(accessed), copy.deepcopy(lockset), kind))
        elif isinstance(value, (gcc.IntegerCst, gcc.AddrExpr, gcc.Constructor)):
            # nothing to do
            pass
        else:
            raise Exception('Unexpected value: {}'.format(repr(value)))



ps = RaceFinder(name='race-finder')
ps.register_after('whole-program')

