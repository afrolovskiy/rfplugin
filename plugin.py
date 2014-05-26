from pprint import pprint
import random
import copy
import time
import json

import gcc


def count_repetitions(array, value):
    count = 0
    for element in array:
        if element == value:
            count = count + 1
    return count


class ToDict(object):
    def to_dict(self):
        result = {}
        for field in self.fields:
            value = getattr(self, field)
            if hasattr(value, '__iter__'):
                result[field] = []
                for element in value:
                    if hasattr(element, 'to_dict'):
                        result[field].append(element.to_dict())
                    else:
                        result[field].append(str(element))
            elif hasattr(value, 'to_dict'):
                result[field] = value.to_dict()
            else:
                result[field] = str(value)
        return result
 

class RelativeLockset(ToDict):
    fields = ('acquired', 'released')

    def __init__(self, acquired=None, released=None):
        self.acquired = acquired or set()
        self.released = released or set()

    def __hash__(self):
        acquired = sum([hash(l) for l in self.acquired])
        released = sum([hash(l) for l in self.released])
        return acquired + 5 * released

    def __eq__(self, other):
        return hash(self) == self(other)

    def acquire(self, lock):
        if lock in self.released:
            self.released.remove(lock)
        self.acquired.add(lock)

    def release(self, lock):
        if lock in self.acquired:
            self.acquired.remove(lock)
        else:
            self.released.add(lock)

    def summary(self, lockset):
        self.acquired = self.acquired.intersection(lockset.acquired)
        self.released = self.released.union(lockset.released)

    def update(self, lockset):
        self.acquired = self.acquired.union(lockset.acquired).difference(lockset.released)
        self.released = self.released.union(lockset.released).difference(lockset.acquired)


class GuardedAccess(ToDict):
    fields = ('access', 'lockset', 'kind', 'file', 'line')
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

    @staticmethod
    def new(location, stat, kind, context):
        return GuardedAccess(
            copy.deepcopy(location),
            copy.deepcopy(context.lockset),
            kind,
            stat.loc.file,
            stat.loc.line
        )



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


class Type(ToDict):
    fields = ('name',)

    def __init__(self, name):
        self.name = name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return hash(self) == hash(other)


class PointerType(Type):
    fields = ('name', 'type')

    def __init__(self, type):
        super(PointerType, self).__init__(name='pointer')
        self.type = type

    def __hash__(self):
        return hash(self.name) + 3 * hash(self.type)


class Location(ToDict):
    fields = ('name', 'type', 'visibility', 'status', 'area', 'value')

    VISIBILITY_GLOBAL = 'global'
    VISIBILITY_LOCAL = 'local'
    VISIBILITY_FORMAL = 'formal'

    STATUS_COMMON = 'common'
    STATUS_FAKE = 'fake'
    STATUS_TEMP = 'temp'

    def __init__(self, name, type, visibility, status, value=None, area=None):
        self.name = name
        self.type = type
        self.visibility = visibility
        self.status = status
        self.value = value
        self.area = area

    def __hash__(self):
        return (hash(self.name) + 2 * hash(self.type) + 3 * hash(self.visibility) +
                4 * hash(self.status) + hash(self.area))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def is_shared(self):
        return self.visibility in (self.VISIBILITY_GLOBAL, self.VISIBILITY_FORMAL)

    def is_global(self):
        return self.visibility == self.VISIBILITY_GLOBAL

    def is_formal(self):
        return self.visibility == self.VISIBILITY_FORMAL

    def is_fake(self):
        return self.status == self.STATUS_FAKE


class Address(ToDict):

    def __init__(self, location):
        self.location = location

    def __hash__(self):
        return 2 * hash(self.location)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def to_dict(self):
        return {
            'address_of': self.location.to_dict()
        }


class Value(ToDict):
    fields = ('id',)
    ID_RANGE = (0, 10000)

    def __init__(self):
        self.id = random.randint(*self.ID_RANGE)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return hash(self) == hash(other)


class PathContext(object):
    def __init__(self, fun, variables, lockset, accesses):
        self.fun = fun
        self.variables = variables
        self.lockset = lockset
        self.accesses = accesses


class Warning(ToDict):
    fields = ('variable', 'visibility', 'function', 'line')

    def __init__(self, variable, visibility, function, line):
        self.variable = variable
        self.visibility = visibility
        self.function = function
        self.line = line

    def __hash__(self):
        return (hash(self.variable) + hash(self.visibility) +
                hash(self.function) + hash(self.line))

    def __eq__(self, other):
        return hash(self) == hash(other)


class FunctionSummary(ToDict):
    fields = ('lockset', 'accesses', 'formals', 'variables')

    def __init__(self, fname, lockset, accesses, formals, variables):
        self.fname = fname
        self.lockset = lockset
        self.accesses = accesses
        self.formals = formals
        self.variables = variables


class RaceFinder(gcc.IpaPass):
    FAKE_RANGE = (0, 10000)
    MAX_LEVEL = 4

    def __init__(self, *args, **kwargs):
        super(RaceFinder, self).__init__(*args, **kwargs)
        self.summaries = {}
        self.global_variables = {}
        self.entries = []

    def execute(self, *args, **kwargs):
        start_time = time.time()

        # initialize global variables
        self.global_variables = self.init_global_variables()

        # analyze functions
        for node in gcc.get_callgraph_nodes():
            if not self.is_analyzed(node):
                self.analyze_node(node)

        # generate warnings
        warnings = self.find_races()

        for warn in warnings:
            msg = ('WARNING: Race condition when accessing '
                   'the variable {variable} ({visibility}) in {function} '
                   'on line {line}')
            print msg.format(**warn.to_dict())

        elapsed_time = time.time() - start_time
        print 'Elapsed time: {} ms'.format(elapsed_time * 1000)

    def init_global_variables(self):
        global_variables = {}
        for variable in gcc.get_variables():
            name, type = variable.decl.name, variable.decl.type
            global_variables[name] = self.init_variable(
                name, type, visibility=Location.VISIBILITY_GLOBAL)
        return global_variables

    def init_variable(self, name, type, visibility=None, status=None, area=None):
        visibility = visibility or Location.VISIBILITY_LOCAL
        status = status or Location.STATUS_COMMON

        if isinstance(type, gcc.PointerType):
            faked_name = '{}_fake_{}'.format(name, random.randint(*self.FAKE_RANGE))
            faked_location = self.init_variable(
               faked_name, type.type,
               visibility=visibility,
               status=Location.STATUS_FAKE,
               area=area
            )
            return Location(
                name=name,
                visibility=visibility,
                status=status,
                type=PointerType(type=faked_location.type),
                value=Address(faked_location),
                area=area
            )

        return Location(
            name=name,
            type=Type(name=str(type)),
            visibility=visibility,
            status=status,
            value = Value(),
            area=area
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
        fun = node.decl.function
        self.print_info(fun)  # for debug
        #if fun.decl.name == 'munge':
        #    import ipdb; ipdb.set_trace()

        variables = self.init_variables(fun)

        lockset_summary, access_summary = None, None

        pathes = self.build_pathes(fun)
        for path in pathes:
            lockset, access_table = self.analyze_path(fun, path, copy.deepcopy(variables))

            if lockset_summary is None:
                lockset_summary = lockset
            else:
                lockset_summary.summary(lockset)

            if access_summary is None:
                access_summary = access_table
            else:
                access_summary.update(access_table)

        self.summaries[fun.decl.name] = FunctionSummary(
            fname=fun.decl.name,
            lockset=lockset_summary,
            accesses=access_summary,
            formals=[variables[str(arg)] for arg in fun.decl.arguments],
            variables=variables
        )

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
        accesses = GuardedAccessTable()
        context = PathContext(fun, variables, lockset, accesses)

        for block in path:
            for stat in block.gimple:
                self.analyze_statement(stat, context)

        return lockset, accesses

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
                name, type, visibility=Location.VISIBILITY_FORMAL,
                area=str(fun.decl))
        return formal_parameters

    def init_local_variables(self, fun):
        local_variables = {}
        for decl in fun.local_decls:
            name, type = str(decl), decl.type
            local_variables[name] = self.init_variable(
                name, type, visibility=Location.VISIBILITY_LOCAL,
                area=str(fun.decl))
        return local_variables

    def analyze_statement(self, stat, context):
        self.analyze_access(stat, context)
        self.analyze_aliases(stat, context)
        if isinstance(stat, gcc.GimpleCall):
            self.analyze_call(stat, context)

    def analyze_access(self, stat, context):
        if isinstance(stat, gcc.GimpleAssign):
            # analyze left side of assignment
            self.analyze_value(stat.lhs, stat, context, GuardedAccess.WRITE)

            # analyze right side of assign
            for rhs in stat.rhs:
                self.analyze_value(rhs, stat, context, GuardedAccess.READ)

        elif isinstance(stat, gcc.GimpleCall):
            if stat.lhs:
                # analyze lhs
                self.analyze_value(stat.lhs, stat, context, GuardedAccess.WRITE)

            # analyze function arguments
            for rhs in stat.args:
                self.analyze_value(rhs, stat, context, GuardedAccess.READ)

        elif isinstance(stat, gcc.GimpleReturn):
            if stat.retval:
                # analuze returned value
                self.analyze_value(stat.retval, stat, context, GuardedAccess.READ)

        elif (isinstance(stat, gcc.GimpleCond) and stat.exprcode in
                (gcc.EqExpr, gcc.NeExpr, gcc.LeExpr, gcc.LtExpr, gcc.GeExpr, gcc.GtExpr,)):
            # analyze left and right side of compare expression
            self.analyze_value(stat.lhs, stat, context, GuardedAccess.READ)
            self.analyze_value(stat.rhs, stat, context, GuardedAccess.READ)

        elif isinstance(stat, gcc.GimpleLabel):
            # do nothing
            pass

        else:
            raise Exception('Unhandled statement: {}'.format(repr(stat)))

    def analyze_value(self, value, stat, context, kind):
        if isinstance(value, (gcc.SsaName, gcc.VarDecl, gcc.ParmDecl)):
            # p
            location = self.get_location(value, context)
            if location.is_global():
                ga = GuardedAccess.new(location, stat, kind, context)
                context.accesses.add(ga)

        elif isinstance(value, gcc.MemRef):
            # *p
            location = self.get_location(value.operand, context)  # p
            if location.is_global():
                ga = GuardedAccess.new(location, stat, GuardedAccess.READ, context)
                context.accesses.add(ga)

            location = location.value.location  # *p
            if location.is_shared():
                ga = GuardedAccess.new(location, stat, kind, context)
                context.accesses.add(ga)

        elif value is None or isinstance(value, (gcc.IntegerCst, gcc.AddrExpr, gcc.Constructor)):
            # do nothing
            pass

        else:
            raise Exception('Unexpected value: {}'.format(repr(value)))

    def get_name(self, value):
        if isinstance(value, gcc.SsaName) and (value.var is not None):
            return str(value.var)
        return str(value)

    def get_location(self, value, context):
        name = self.get_name(value)
        locations = context.variables
        if (isinstance(value, gcc.SsaName) and
                (value.var is None) and (name not in locations)):
            # create location for temp variable
            locations[name] = Location(
                name=name,
                type=None,
                visibility=Location.VISIBILITY_LOCAL,
                status=Location.STATUS_TEMP,
                area=context.fun.decl.name
            )
        return locations[name]

    def analyze_aliases(self, stat, context):
        # analyze only simple assignment statements
        if not (isinstance(stat, gcc.GimpleAssign) and len(stat.rhs) == 1):
            return

        lhs, rhs = stat.lhs, stat.rhs[0]
        variables = context.variables

        if isinstance(lhs, gcc.MemRef):  # *p
            llocation = self.get_location(lhs.operand, context).value.location

            if isinstance(rhs, gcc.AddrExpr):
                # *p = &q
                #        q
                #        ^   
                #        |
                # p ---> r
                rlocations = self.get_location(rhs.operand, context)
                llocation.value = Address(rlocation)
            elif isinstance(rhs, gcc.MemRef):
                # *p = *q
                # q ---> b ---> c
                #               ^
                #               |
                #        p ---> a
                rlocation = self.get_location(rhs.operand, context).value.location
                llocation.value = rlocation.value
            elif isinstance(rhs, (gcc.VarDecl, gcc.ParmDecl, gcc.SsaName)):
                # *p = q
                # q ---> b
                #        ^
                #        |
                # p ---> r
                rlocation = self.get_location(rhs, context)
                llocation.value = rlocation.value
            elif isinstance(rhs, (gcc.IntegerCst, gcc.Constructor)):
                # do nothing
                pass
            else:
                raise Exception("Unexpected rhs: {}".format(repr(rhs)))

        elif isinstance(lhs, (gcc.VarDecl, gcc.ParmDecl, gcc.SsaName)):  # p
            llocation = self.get_location(lhs, context)

            if isinstance(rhs, gcc.AddrExpr):
                # p = &q
                # p ---> q
                rlocation = self.get_location(rhs.operand, context)
                llocation.value = Address(rlocation)
            elif isinstance(rhs, gcc.MemRef):
                # p = *q
                # q ---> a ---> b
                #               ^
                #               |
                #               p
                rlocation = self.get_location(rhs.operand, context).value.location
                llocation.value = rlocation.value
            elif isinstance(rhs, (gcc.SsaName, gcc.VarDecl, gcc.ParmDecl)):
                # p = q
                # q ---> a
                #        ^
                #        |
                #        p
                rlocation = self.get_location(rhs, context)
                llocation.value = rlocation.value
            elif isinstance(rhs, (gcc.IntegerCst, gcc.Constructor)):
                # nothing to do
                pass
            else:
                raise Exception("Unexpected rhs: {}".format(repr(rhs)))

        else:
            raise Exception("Unexpected lhs: {}".format(repr(lhs)))

    def analyze_call(self, stat, context):
        fname = str(stat.fndecl)
        if fname in ('pthread_mutex_lock', 'sem_init'):
            arg = stat.args[0]
            if isinstance(arg, gcc.AddrExpr):
                location = self.get_location(arg.operand, context)
                context.lockset.acquire(Address(location))
            elif isinstance(arg, (gcc.SsaName, gcc.VarDecl, gcc.ParmDecl)):
                location = self.get_location(arg, context)
                context.lockset.acquire(location.value)
            else:
                raise Exception('Unexpexted argument of {}: {}'.format(fname, repr(arg)))
        
        elif fname in ('pthread_mutex_unlock', 'sem_pos'):
            arg = stat.args[0]
            if isinstance(arg, gcc.AddrExpr):
                location = self.get_location(arg.operand, context)
                context.lockset.release(Address(location))
            elif isinstance(arg, (gcc.SsaName, gcc.VarDecl, gcc.ParmDecl)):
                location = self.get_location(arg, context)
                context.lockset.release(location.value)
            else:
                raise Exception('Unexpexted argument of {}: {}'.format(fname, repr(arg)))

        elif fname == 'pthread_create':
            entry = str(stat.args[2].operand)
            summary = self.summaries.get(entry)
            if summary is None:
                node = self.get_node_by_name(entry)
                if node is None:
                    raise Exception('Create thread with unknown function: {}'.format(entry))
                self.analyze_node(node)
                summary = self.summaries[entry]
            summary = self.rebind_summary(summary, [stat.args[3],], context)
            self.entries.append({'name': entry, 'accesses': summary.accesses})

        else:
            summary = self.summaries.get(fname)
            if summary is None:
                node = self.get_node_by_name(fname)
                if node is None:
                    # pass call of external function
                    return
                self.analyze_node(node)
                summary = self.summaries[fname]
            summary = self.rebind_summary(summary, stat.args, context)
            # update current lockset and access table
            context.lockset.update(summary.lockset)
            context.accesses.update(summary.accesses)

    def rebind_summary(self, summary, args, context):
        summary = copy.deepcopy(summary)

        # rebind guarded access table
        for ga in summary.accesses.accesses:
            if ga.access.is_formal():
                # rebind accessed location
                ga.access = copy.deepcopy(self.find_rebinding_location(ga.access, args, summary.formals, context))

            # rebind relative lockset
            ga.lockset = self.rebind_lockset(ga.lockset, args, summary.formals, context)

        # rebind function relative lockset summary
        summary.lockset = self.rebind_lockset(summary.lockset, args, summary.formals, context)

        return summary

    def find_rebinding_location(self, location, arguments, formals, context):
        fidx, level = self.find_parent(location, formals)
        if fidx is None or level is None:
            import ipdb; ipdb.set_trace()
            raise Exception('Critical error')

        arg = arguments[fidx]
        if isinstance(arg, gcc.AddrExpr):
            old_location = self.get_location(arg.operand, context)
            new_location = Location(
                name=str(arg),
                type=PointerType(type=old_location.type),
                area=old_location.area,
                status=Location.STATUS_FAKE,
                visibility=old_location.visibility,
                value=Address(old_location)
            )
        else:
            new_location = self.get_location(arg, context)

        for lid in range(level):
            new_location = new_location.value.location

        return new_location

    def find_parent(self, location, formals):
        #if location.name.startswith('pcount'):
        #    import ipdb; ipdb.set_trace()
        for idx in range(len(formals)):
            formal, level = formals[idx], 0

            while True:
                if formal == location:
                    return idx, level

                if isinstance(formal, Value):
                    break

                formal = formal.value.location

                level = level + 1

        return None, None

    def rebind_lockset(self, lockset, args, formals, variables):
        return RelativeLockset(
            self.rebind_set(lockset.acquired, args, formals, variables),
            self.rebind_set(lockset.released, args, formals, variables)
        )

    def rebind_set(self, old_set, args, formals, variables):
        new_set = set()
        for value in old_set:
            need_address = False

            if isinstance(value, Address):
                value = value.location

            if value.is_formal():
                value = self.find_rebinding_location(value, args, formals, variables)

            if need_address:
                value = Address(value)

            new_set.add(copy.deepcopy(value))

        return new_set

    def find_races(self):
        warnings = set()
        for idx1 in range(len(self.entries) - 1):
            for idx2 in range(idx1 + 1, len(self.entries)):
                warnings = warnings.union(self.compare_accesses(self.entries[idx1], self.entries[idx2]))
        return warnings

    def compare_accesses(self, entry1, entry2):
        warnings = set()
        for ga1 in entry1['accesses'].accesses:
            for ga2 in entry2['accesses'].accesses:
                if self.has_race(ga1, ga2):
                    warnings.add(Warning(
                        variable=ga1.access.name,
                        visibility=ga1.access.visibility,
                        function=entry1['name'],
                        line=ga1.line
                    ))
                    warnings.add(Warning(
                        variable=ga2.access.name,
                        visibility=ga2.access.visibility,
                        function=entry2['name'],
                        line=ga2.line
                    ))
        return warnings

    def has_race(self, ga1, ga2):
        return (ga1.access == ga2.access and
                (ga1.kind == GuardedAccess.WRITE or ga2.kind == GuardedAccess.WRITE) and
                len(ga1.lockset.acquired.intersection(ga2.lockset.acquired)) == 0)


ps = RaceFinder(name='race-finder')
ps.register_after('whole-program')

