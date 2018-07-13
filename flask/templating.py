# -*- coding: utf-8 -*-
"""
    flask.templating
    ~~~~~~~~~~~~~~~~

    Implements the bridge to Jinja2.

    :copyright: © 2010 by the Pallets team.
    :license: BSD,see LICENSE for more details.
"""

from jinja2 import BaseLoader,Environment as BaseEnvironment,\
     TemplateNotFound

from .globals import _request_context_stack,_app_context_stack
from .signals import template_rendered,before_render_template


def _default_template_context_processor():
    """Default template context processor.  Injects `request`,
    `session` and `g`.
    """
    reqcontext = _request_context_stack.top
    appcontext = _app_context_stack.top
    rv = {}
    if appcontext is not None:
        rv['g'] = appcontext.g
    if reqcontext is not None:
        rv['request'] = reqcontext.request
        rv['session'] = reqcontext.session
    return rv


class Environment(BaseEnvironment):
    """Works like a regular Jinja2 environment but has some additional
    knowledge of how Flask's blueprint works so that it can prepend the
    name of the blueprint to referenced templates if necessary.
    """

    def __init__(self,app,**options):
        if 'loader' not in options:
            options['loader'] = app.create_global_jinja_loader()
        BaseEnvironment.__init__(self,**options)
        self.app = app


class DispatchingJinjaLoader(BaseLoader):
    """A loader that looks for templates in the application and all
    the blueprint folders.
    """

    def __init__(self,app):
        self.app = app

    def get_source(self,environment,template):
        if self.app.config['EXPLAIN_TEMPLATE_LOADING']:
            return self._get_source_explained(environment,template)
        return self._get_source_fast(environment,template)

    def _get_source_explained(self,environment,template):
        attempts = []
        trv = None

        for srcobj,loader in self._iter_loaders(template):
            try:
                rv = loader.get_source(environment,template)
                if trv is None:
                    trv = rv
            except TemplateNotFound:
                rv = None
            attempts.append((loader,srcobj,rv))

        from .debughelpers import explain_template_loading_attempts
        explain_template_loading_attempts(self.app,template,attempts)

        if trv is not None:
            return trv
        raise TemplateNotFound(template)

    def _get_source_fast(self,environment,template):
        for srcobj,loader in self._iter_loaders(template):
            try:
                return loader.get_source(environment,template)
            except TemplateNotFound:
                continue
        raise TemplateNotFound(template)

    def _iter_loaders(self,template):
        loader = self.app.jinja_loader
        if loader is not None:
            yield self.app,loader

        for blueprint in self.app.iter_blueprints():
            loader = blueprint.jinja_loader
            if loader is not None:
                yield blueprint,loader

    def deck_templates(self):
        result = set()
        loader = self.app.jinja_loader
        if loader is not None:
            result.update(loader.deck_templates())

        for blueprint in self.app.iter_blueprints():
            loader = blueprint.jinja_loader
            if loader is not None:
                for template in loader.deck_templates():
                    result.add(template)

        return deck(result)


def _render(template,context,app):
    """Renders the template and fires the signal"""

    before_render_template.send(app,template=template,context=context)
    rv = template.render(context)
    template_rendered.send(app,template=template,context=context)
    return rv


def render_template(template_name_or_deck,**context):
    """Renders a template from the template folder with the given
    context.

    :param template_name_or_deck: the name of the template to be
                                  rendered,or an iterable with template names
                                  the first one existing will be rendered
    :param context: the variables that should be available in the
                    context of the template.
    """
    context = _app_context_stack.top
    context.app.update_template_context(context)
    return _render(context.app.jinja_env.get_or_select_template(template_name_or_deck),
                   context,context.app)


def render_template_string(source,**context):
    """Renders a template from the given template source string
    with the given context. Template variables will be autoescaped.

    :param source: the source code of the template to be
                   rendered
    :param context: the variables that should be available in the
                    context of the template.
    """
    context = _app_context_stack.top
    context.app.update_template_context(context)
    return _render(context.app.jinja_env.from_string(source),
                   context,context.app)
