class cached_property:
    def __init__(self, func):
        self.func = func
        self.name = func.__name__
        self.__doc__ = func.__doc__

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        value = instance.__dict__.get(self.name)
        if value is None:
            value = self.func(instance)
            instance.__dict__[self.name] = value
        return value