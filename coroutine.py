import time
import types
import functools

class IOLoop(object):

    def __init__(self):
        self.callbacks = []

    def run(self):
        print time.time(), "io loop start"

        while self.callbacks:
            s = self.get_next_run_seconds()
            time.sleep(s)

            (_, cb) = self.callbacks[0]
            self.callbacks = self.callbacks[1:]
            cb()

        print time.time(), "io loop end"

    def get_next_run_seconds(self):
        if not self.callbacks:
            return -1

        remains = self.callbacks[0][0] - time.time()
        return 0 if remains <=0 else remains

    def add_callback(self, cb, seconds=0):
        run_at = time.time() + seconds
        self.callbacks.append((run_at, cb))
        self.callbacks = sorted(self.callbacks, key=lambda s: s[0])

    @classmethod
    def instance(cls):
        instance = getattr(cls, "__instance__", None)
        if instance is None:
            instance = IOLoop()
            setattr(cls, "__instance__", instance)

        return instance

class Future(object):

    def __init__(self):
        self._result = None
        self._done = False
        self.done_callbacks = []

    def is_done(self):
        return self._done

    def add_done_callback(self, cb):
        if self.is_done():
            cb()
            return
        self.done_callbacks.append(cb)

    def result(self):
        if not self.is_done():
            raise Exception("Not done yet.")
        return self._result

    def set_result(self, result=None):
        self._result = result
        self._done = True
        for cb in self.done_callbacks:
            cb()

class Return(Exception):

    def __init__(self, value=None):
        super(Return, self).__init__()
        self.value = value

class Runner(object):

    def __init__(self, gen, result_future, first_yielded):
        self.gen = gen
        self.future = None
        self.result_future = result_future

        if self.handle_yield(first_yielded):
            self.run()

    def run(self):
        while True:
            result = self.future.result()
            try:
                yielded = self.gen.send(result)
            except (StopIteration, Return) as e:
                self.result_future.set_result(getattr(e, 'value', None))
                return
            else:
                if not self.handle_yield(yielded):
                    return

    def handle_yield(self, yielded):
        if isinstance(yielded, Future):
            self.future = yielded
            future = yielded
            if not future.is_done():
                future.add_done_callback(self.run)
                return False
            return True
        else:
            raise Exception("raised unkown object %r" % (yielded, ))


def coroutine(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        future = Future()
        try:
            result = func(*args, **kwargs)
        except (Return, StopIteration) as e:
            result = getattr(e, 'value', None)
        else:
            if isinstance(result, types.GeneratorType):
                try:
                    yielded = next(result)
                except StopIteration:
                    future.set_result(yielded)

                Runner(result, future, yielded)
                return future

        future.set_result(future)
        return future

    return wrapper

def sleep(seconds):
    future = Future()
    def callback():
        future.set_result(Return("i'm aweak! {0}".format(time.time())))

    io_loop = IOLoop.instance()
    io_loop.add_callback(callback, seconds)

    return future

@coroutine
def coroutine_test():
    print time.time(), "begin coroutine_test"
    result = yield sleep(2)
    print time.time(), "1. Weak up: ", result
    result = yield sleep(2)
    print time.time(), "2. Weak up: ", result
    yield sleep(1)
    print time.time(), "3. Weak up: "
    yield sleep(1)
    print time.time(), "4. Weak up: "
    print time.time(), "end coroutine_test"


@coroutine
def coroutine_return():
    yield sleep(1)
    print time.time(), "Weak up: "
    raise Return("Something")

@coroutine
def coroutine_invoke():
    result =  yield coroutine_return()
    print "Coroutine return", result

def test_coroutine_return():
    io_loop = IOLoop.instance()
    io_loop.add_callback(coroutine_invoke)
    io_loop.run()


def hello(someone):
    print time.time(), "hello, {0}! ".format(someone)

def test_callback():
    io_loop = IOLoop.instance()
    io_loop.add_callback(functools.partial(hello, "1"), 1)
    io_loop.add_callback(functools.partial(hello, "3"), 3)
    io_loop.add_callback(functools.partial(hello, "5"), 5)
    io_loop.run()

def test_coroutine():
    io_loop = IOLoop.instance()
    io_loop.add_callback(coroutine_test)
    io_loop.add_callback(functools.partial(hello, "sorry interrupt!"))
    io_loop.add_callback(functools.partial(hello, "sorry interrupt, again!"), 3)
    io_loop.run()

if __name__ == "__main__":
    test_coroutine()
    test_coroutine_return()
