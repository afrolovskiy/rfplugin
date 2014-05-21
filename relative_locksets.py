import gcc


def count_repeat(value, array):
    count = 0
    for element in array:
        if element == value:
            count = count + 1
    return count


# TODO: not function in source file must be placed in calling sequence from down to top, need fix it
class RelativeLocksetAnalyzer(gcc.GimplePass):
    K = 2

    def __init__(self, *args, **kwargs):
        super(RelativeLocksetAnalyzer, self).__init__(*args, **kwargs)

    def execute(self, fun):
        #print '================================'
        #print fun.decl.name
        #for bb in fun.cfg.basic_blocks:
        #    for edge in bb.succs:
        #        print '({},{})'.format(bb.index, edge.dest.index)
        core = self.build_code(fun)

        entry = fun.cfg.entry
        path = []
        relative_lockset = (set(), set())
        summary = (set(), set())
        self.walk_block(entry, path, relative_lockset, summary, fun)


    @staticmethod
    def build_code(fun):
        def walk(block, path):
            path.append(block.index)

            if block.index == fun.cfg.exit.index:
                return set(path)

            cores = []
            for edge in block.succs:
                next_block = edge.dest
                if count_repeat(next_block.index, path) <= RelativeLocksetAnalyzer.K:
                    cores.append(walk(next_block, list(path)))

            cores = [c for c in cores if c is not None]
            count = len(cores)

            if count == 0:
                return None

            core = cores[0]
            for idx in range(1, count):
                core = core.intersection(cores[idx])

            return core

        return walk(fun.cfg.entry, [])

    def walk_block(self, block, path, relative_lockset, summary, fun):
        if count_repeat(block.index, path) > RelativeLocksetAnalyzer.K:
            return

        path.append(block.index)
        self.analyze_block(block, relative_lockset)

        if block.index == fun.cfg.exit.index:
            # modify_summary
            return

        for edge in block.succs:
            self.walk_block(block, list(path)

    def analyze_block(self, block, relative_lockset):
        pass



ps = RelativeLocksetAnalyzer(name='relative-lockset')
ps.register_after('cfg')

