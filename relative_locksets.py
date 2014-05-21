import gcc


class RelativeLocksetAnalyzer(gcc.GimplePass):
    K = 2

    def execute(self, fun):
        core = self.build_code(fun)

    @staticmethod
    def build_code(fun):
        def count_block(block, path):
            count = 0
            for idx in path:
                if idx == block.index:
                    count = count + 1
            return count

        def walk(block, path):
            path.append(block.index)

            if block.index == fun.cfg.exit.index:
                return set(path)

            cores, count = [], 0
            for edge in block.succs:
                next_block = edge.dest
                if count_block(next_block, path) <= RelativeLocksetAnalyzer.K:
                    cores.append(walk(next_block, list(path)))
                    count = count + 1

            core = cores[0]
            for idx in range(1, count):
                core = core.intersection(cores[idx])

            return core

        return walk(fun.cfg.entry, [])


ps = RelativeLocksetAnalyzer(name='relative-lockset')
ps.register_after('cfg')

