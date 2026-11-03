"""Tiny source interpreter for prepared Flask/Django patterns. No exec/import of answers."""
from __future__ import annotations

import ast
from dataclasses import dataclass


class Unsupported(ValueError):
    pass


@dataclass
class Reply:
    body: dict
    status: int = 200


@dataclass
class Query:
    values: dict


ERRORS = {'TypeError': TypeError, 'ValueError': ValueError, 'KeyError': KeyError}
RESERVED = set(ERRORS) | {'int'}


class SourceCheck:
    def __init__(self, codes, mode):
        self.mode, self.steps = mode, 0
        self.trees = [ast.parse(code) for code in codes]
        self.imports, self.functions, self.globals = {}, {}, {}
        for index, tree in enumerate(self.trees):
            stack = [(tree, 0)]; count = 0
            while stack:
                node, depth = stack.pop(); count += 1
                if count > 4000 or depth > 60: raise Unsupported('source size')
                stack.extend((child, depth+1) for child in ast.iter_child_nodes(node))
            imports = self.imports[index] = {}
            local_names = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom):
                    for item in node.names:
                        if item.name == '*': raise Unsupported('star import')
                        self._import(imports, item.asname or item.name, '.'*node.level+(node.module or '')+'.'+item.name)
                elif isinstance(node, ast.Import):
                    for item in node.names:
                        self._import(imports, item.asname or item.name.split('.')[0], item.name if item.asname else item.name.split('.')[0])
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if isinstance(node, ast.AsyncFunctionDef) or node.name in self.functions: raise Unsupported('ambiguous function')
                    self.functions[node.name] = (node, index); local_names.add(node.name)
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            if (index, target.id) in self.globals or target.id in RESERVED: raise Unsupported('ambiguous binding')
                            self.globals[index, target.id] = node.value; local_names.add(target.id)
            if local_names & imports.keys(): raise Unsupported('shadowed import')

    @staticmethod
    def _import(imports, name, qualified):
        if name in RESERVED or name in imports and imports[name] != qualified: raise Unsupported('import binding')
        imports[name] = qualified

    def qualified(self, node, source):
        if isinstance(node, ast.Name): return self.imports[source].get(node.id, '')
        if isinstance(node, ast.Attribute):
            prefix = self.qualified(node.value, source)
            return prefix+'.'+node.attr if prefix else ''
        return ''

    def function(self, node, source):
        if isinstance(node, ast.Name) and node.id in self.functions and self.functions[node.id][1] == source:
            return self.functions[node.id]
        qualified = self.qualified(node, source)
        name = qualified.rsplit('.', 1)[-1]
        if name in self.functions and not qualified.startswith(('flask.', 'django.')):
            return self.functions[name]
        raise Unsupported('unresolved helper')

    def endpoint(self, task):
        if self.mode == 'flask':
            for fn, source in self.functions.values():
                for decorator in fn.decorator_list:
                    if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                            and isinstance(decorator.func.value, ast.Name) and decorator.args
                            and isinstance(decorator.args[0], ast.Constant) and decorator.args[0].value == task['route']): continue
                    app = self.globals.get((source, decorator.func.value.id))
                    if not isinstance(app, ast.Call) or self.qualified(app.func, source) != 'flask.Flask': continue
                    methods = next((k.value for k in decorator.keywords if k.arg == 'methods'), None)
                    get_only = methods is None or isinstance(methods, (ast.List, ast.Tuple)) and [getattr(n,'value',None) for n in methods.elts] == ['GET']
                    if decorator.func.attr == 'get' and methods is None or decorator.func.attr == 'route' and get_only: return fn, source
        else:
            for (source, name), node in self.globals.items():
                if name != 'urlpatterns' or not isinstance(node, (ast.List, ast.Tuple)): continue
                for call in node.elts:
                    if not (isinstance(call, ast.Call) and self.qualified(call.func, source) == 'django.urls.path'
                            and len(call.args) >= 2 and isinstance(call.args[0], ast.Constant)
                            and '/'+str(call.args[0].value) == task['route']): continue
                    fn, origin = self.function(call.args[1], source)
                    if any(self.qualified(d, origin) == 'django.views.decorators.http.require_GET' for d in fn.decorator_list): return fn, origin
        return None

    def tick(self, depth):
        self.steps += 1
        if depth > 30 or self.steps > 1500: raise Unsupported('interpretation budget')

    def bind(self, target, value, env):
        if isinstance(target, ast.Name) and target.id not in RESERVED: env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, tuple) and len(target.elts) == len(value):
            for name, item in zip(target.elts, value): self.bind(name, item, env)
        else: raise Unsupported('assignment')

    def invoke(self, function, args, keywords=None, depth=0):
        self.tick(depth)
        fn, source = function; names = fn.args.posonlyargs + fn.args.args
        if fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or len(args) > len(names): raise Unsupported('function signature')
        env = {}; keywords = dict(keywords or {})
        for index, name in enumerate(names):
            if index < len(args):
                if name.arg in keywords: raise Unsupported('duplicate argument')
                item = args[index]
            elif name.arg in keywords: item = keywords.pop(name.arg)
            elif index >= len(names)-len(fn.args.defaults): item = self.value(fn.args.defaults[index-len(names)], env, source, depth+1)
            else: raise Unsupported('missing argument')
            self.bind(ast.Name(id=name.arg), item, env)
        if keywords: raise Unsupported('unknown argument')
        return self.run(fn.body, env, source, depth+1)[1]

    def value(self, node, env, source, depth):
        self.tick(depth)
        walk = lambda n: self.value(n, env, source, depth+1)
        if isinstance(node, ast.Constant) and (type(node.value) in (int, str, bool) or node.value is None):
            if type(node.value) is int and abs(node.value) > 10**8: raise Unsupported('constant range')
            return node.value
        if isinstance(node, ast.Name):
            if node.id in env: return env[node.id]
            if self.qualified(node, source) == 'flask.request': return env['__request__']
            if (source, node.id) in self.globals: return walk(self.globals[source, node.id])
        if isinstance(node, ast.Attribute):
            if self.qualified(node, source) == 'flask.request': return env['__request__']
            obj = walk(node.value)
            if type(obj) is dict and node.attr in ('GET','args','method'): return obj[node.attr]
        if isinstance(node, ast.Subscript):
            obj, key = walk(node.value), walk(node.slice)
            if isinstance(obj, Query) and type(key) is str: return obj.values[key]
        if isinstance(node, ast.Dict) and len(node.keys) <= 8 and all(k is not None for k in node.keys):
            return {walk(k):walk(v) for k,v in zip(node.keys,node.values)}
        if isinstance(node, ast.Tuple): return tuple(walk(n) for n in node.elts)
        if isinstance(node, ast.UnaryOp):
            item = walk(node.operand)
            if isinstance(node.op, ast.Not): return not item
            if isinstance(node.op, ast.USub) and type(item) is int: return -item
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add,ast.Sub,ast.Mult)):
            a,b = walk(node.left),walk(node.right)
            if type(a) is not int or type(b) is not int or max(abs(a),abs(b)) > 10**10: raise Unsupported('arithmetic')
            return a+b if isinstance(node.op,ast.Add) else a-b if isinstance(node.op,ast.Sub) else a*b
        if isinstance(node, ast.Compare):
            left = walk(node.left)
            for op, other in zip(node.ops,node.comparators):
                right = walk(other)
                if type(left) not in (int,str,type(None)) or type(right) not in (int,str,type(None)): raise Unsupported('comparison')
                if isinstance(op,ast.Lt): ok = left < right
                elif isinstance(op,ast.Gt): ok = left > right
                elif isinstance(op,ast.LtE): ok = left <= right
                elif isinstance(op,ast.GtE): ok = left >= right
                elif isinstance(op,(ast.Eq,ast.Is)): ok = left == right
                elif isinstance(op,(ast.NotEq,ast.IsNot)): ok = left != right
                else: raise Unsupported('comparison operator')
                if not ok: return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            for expression in node.values:
                item = walk(expression)
                if isinstance(node.op,ast.Or) and item or isinstance(node.op,ast.And) and not item: return item
            return item
        if isinstance(node,ast.IfExp): return walk(node.body if walk(node.test) else node.orelse)
        if isinstance(node,ast.Call):
            args = [walk(a) for a in node.args]
            if any(k.arg is None for k in node.keywords): raise Unsupported('expanded call')
            kwargs = {k.arg:walk(k.value) for k in node.keywords}
            if isinstance(node.func,ast.Name) and node.func.id == 'int' and len(args) == 1 and not kwargs:
                if type(args[0]) not in (str,int,type(None)): raise TypeError('not an integer input')
                return int(args[0])
            if isinstance(node.func,ast.Attribute) and node.func.attr == 'get':
                obj = walk(node.func.value)
                if isinstance(obj,Query) and 1 <= len(args) <= 2 and type(args[0]) is str and not kwargs:
                    return obj.values.get(args[0], args[1] if len(args) == 2 else None)
            qualified = self.qualified(node.func,source)
            if self.mode == 'flask' and qualified == 'flask.jsonify':
                body = args[0] if len(args) == 1 and not kwargs else kwargs if not args else None
                if type(body) is dict: return Reply(body)
            if self.mode == 'django' and qualified == 'django.http.JsonResponse' and len(args) == 1 and type(args[0]) is dict and not kwargs.keys()-{'status','safe'}:
                status = kwargs.get('status',200)
                if type(status) is int: return Reply(args[0],status)
            target = self.function(node.func,source)
            # Request access remains available only to Flask views, never as Python globals.
            return self.invoke(target,args,kwargs,depth+1)
        raise Unsupported('unsupported expression')

    def run(self, nodes, env, source, depth):
        for node in nodes:
            self.tick(depth)
            if isinstance(node,ast.Return): return True,self.value(node.value,env,source,depth+1)
            if isinstance(node,(ast.Assign,ast.AnnAssign)):
                item = self.value(node.value,env,source,depth+1)
                for target in node.targets if isinstance(node,ast.Assign) else [node.target]: self.bind(target,item,env)
            elif isinstance(node,ast.If):
                branch = node.body if self.value(node.test,env,source,depth+1) else node.orelse
                result = self.run(branch,env,source,depth+1)
                if result[0]: return result
            elif isinstance(node,ast.Try) and not node.finalbody:
                try:
                    result = self.run(node.body,env,source,depth+1)
                except (TypeError,ValueError,KeyError) as error:
                    if isinstance(error,Unsupported): raise
                    handler = None
                    for candidate in node.handlers:
                        names = candidate.type.elts if isinstance(candidate.type,ast.Tuple) else [candidate.type]
                        if any(not isinstance(n,ast.Name) or n.id not in ERRORS for n in names): raise Unsupported('exception pattern')
                        if any(isinstance(error,ERRORS[n.id]) for n in names): handler = candidate; break
                    if handler is None: raise
                    result = self.run(handler.body,env,source,depth+1)
                else:
                    if not result[0]: result = self.run(node.orelse,env,source,depth+1)
                if result[0]: return result
            elif isinstance(node,ast.Pass) or isinstance(node,ast.Expr) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str): pass
            else: raise Unsupported('unsupported statement')
        return False,None

    def response(self, endpoint, query):
        self.steps = 0
        request = {'args':Query(query),'GET':Query(query),'method':'GET'}
        fn, source = endpoint
        if self.mode == 'flask':
            # Bind the trusted request marker only for the view invocation.
            if fn.args.args or fn.args.posonlyargs: raise Unsupported('Flask view arguments')
            result = self.run(fn.body,{'__request__':request},source,0)[1]
        else: result = self.invoke(endpoint,[request])
        if self.mode == 'flask' and isinstance(result,tuple) and len(result) == 2 and type(result[1]) is int:
            result = Reply(result[0].body if isinstance(result[0],Reply) else result[0],result[1])
        if self.mode == 'flask' and type(result) is dict: result = Reply(result)
        if not isinstance(result,Reply) or type(result.body) is not dict: raise Unsupported('response pattern')
        return result
