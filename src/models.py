import pymongo
import datetime

class Model :
    def __init__(self, **kwargs):
        self._id = kwargs.get('_id', None)
        for k in self.__data__ :
            try :
                setattr(self, k, kwargs[k])
            except KeyError :
                try :
                    setattr(self, k, self.__default_data__[k])
                except KeyError :
                    raise TypeError("Expecting keyword argument '%s'" % k)
    def get_all_data(self) :
        return { k : getattr(self, k) for k in self.__data__ }

class Admin(Model) :
    __data__ = ["id", "x"]
    __default_data__ = { "id" : None }

class QTypeRegistry(type) :
    def __init__(cls, name, bases, dct) :
        if hasattr(cls, "typeName") :
            QType.qtype_subclasses[cls.typeName] = cls
        super(QTypeRegistry, cls).__init__(name, bases, dct)

class QType(object) :
    __metaclass__ = QTypeRegistry
    qtype_subclasses = {}
    def __init__(self, text):
        self.text = text
    @classmethod
    def deserialize(cls, d) :
        return cls.qtype_subclasses[d['type']].from_dict(d['text'], d['content'])
    def serialize(self) :
        return {"type" : self.typeName,
                "text" : self.text,
                "content" : self.to_dict()}


class AbstractMultiQType(QType) :
    def __init__(self, text, options) :
        QType.__init__(self, text)
        self.options = options
    @classmethod
    def from_dict(cls, text, d) :
        return cls(text, d['options'])
    def to_dict(self) :
        return {'options' : self.options}

class RadioQType(AbstractMultiQType) :
    typeName = "radio"
class CheckboxQType(AbstractMultiQType) :
    typeName = "checkbox"
class SelectQType(AbstractMultiQType) :
    typeName = "select"

class ScaleQType(QType) :
    typeName = "scale"
    def __init__(self, text, scalecont, scalemin, scalemax, scalestep):
        QType.__init__(self, text)
        self.scalecont = scalecont
        self.scalemin = scalemin
        self.scalemax = scalemax
        self.scalestep = scalestep
    @classmethod
    def from_dict(cls, text, d) :
        return cls(text,
                   scalecont=d['scalecont'],
                   scalemin=d['scalemin'],
                   scalemax=d['scalemax'],
                   scalestep=d['scalestep'])
    def to_dict(self) :
        return { 'scalecont' : self.scalecont,
                 'scalemin' : self.scalemin,
                 'scalemax' : self.scalemax,
                 'scalestep' : self.scalestep }

class TextQType(QType) :
    typeName = "text"
    def __init__(self, text, textlength):
        QType.__init__(self, text)
        self.textlength = textlength
    @classmethod
    def from_dict(cls, text, d) :
        return cls(text,
                   textlength=d['textlength'])
    def to_dict(self) :
        return { 'textlength' : self.textlength }

class GridQType(QType) :
    typeName = "grid"
    def __init__(self, text, rowoptions, coloptions):
        QType.__init__(self, text)
        self.rowoptions = rowoptions
        self.coloptions = coloptions
    @classmethod
    def from_dict(cls, text, d) :
        return cls(text,
                   rowoptions=d['rowoptions'],
                   coloptions=d['coloptions'])
    def to_dict(self) :
        return { 'rowoptions' : self.rowoptions,
                 'coloptions' : self.coloptions }


class CType(object) :
    def __init__(self, name=None, questions=[]) :
        self.name = name
        self.questions = questions
    @classmethod
    def from_dict(cls, d) :
        return CType(d['name'], [QType.deserialize(q) for q in d['questions']])
    def to_dict(self) :
        return {'name' : self.name,
                'questions' : [q.serialize() for q in self.questions]}

class CTypeController(object) :
    def __init__(self, db) :
        self.db = db
        self.db.ctypes.ensure_index('name', unique=True)
    def get_names(self) :
        res = self.db.ctypes.find({}, {'name' : True})
        return [r['name'] for r in res]
    def get_by_name(self, name) :
        d = self.db.ctypes.find_one({'name' : name})
        return CType.from_dict(d)
    def create(self, d) :
        c = CType.from_dict(d)
        self.db.ctypes.insert(c.to_dict())
        return c

class CTask(object) :
    def __init__(self, type_name=None, created=None, responses=None, name=None, content=None, live=False) :
        self.type_name = type_name
        self.created = created
        self.responses = responses
        self.name = name
        self.content = content
        self.live = live
    @classmethod
    def from_dict(cls, d) :
        return CTask(type_name=d['type_name'],
                     created=d['created'],
                     responses=d.get('responses', None),
                     name=d['name'],
                     content=d['content'],
                     live=d['live'])
    def to_dict(self) :
        return {'type_name' : self.type_name,
                'created' : self.created,
                'responses' : self.responses or [],
                'name' : self.name,
                'content' : self.content,
                'live' : self.live}

class CResponse(object) :
    def __init__(self, submitted=None, response=None, worker_name=None) :
        self.submitted = submitted # date
        self.response = response # list of data generated by QType
        self.worker_name = worker_name
    @classmethod
    def from_dict(cls, d) :
        return CResponse(submitted=d['submitted'],
                         response=d['response'],
                         worker_name=d['worker_name'])
    def to_dict(self) :
        return {'submitted' : self.submitted,
                'response' : self.response,
                'worker_name' : self.worker_name}

class CTaskController(object) :
    def __init__(self, db) :
        self.db = db
        self.db.ctasks.ensure_index([('type_name', 1), ('name', 1)],
                                    unique=True)
    def get_names(self, type_name) :
        res = self.db.ctasks.find({'type_name' : type_name}, {'name' : True})
        return [r['name'] for r in res]
    def get_by_name(self, type_name, name) :
        d = self.db.ctasks.find_one({'type_name' : type_name,
                                     'name' : name})
        return CTask.from_dict(d)
    def set_live(self, task, is_live) :
        task.live = is_live
        self.db.ctasks.update({'type_name' : task.type_name,
                               'name' : task.name},
                              {'$set' : {'live' : task.live}})
        return task
    def create(self, ctype, name, content, live=False) :
        c = CTask(type_name=ctype.name,
                  created=datetime.datetime.now(),
                  responses=[],
                  name=name,
                  content=content,
                  live=live)
        self.db.ctasks.insert(c.to_dict())
        return c
    def add_response(self, task, worker_name, response) :
        r = CResponse(submitted=datetime.datetime.now(),
                     response=response,
                     worker_name=worker_name)
        self.db.ctasks.update({'type_name' : task.type_name,
                               'name' : task.name},
                              {'$push' : {'responses' : r.to_dict()}})
        return r
