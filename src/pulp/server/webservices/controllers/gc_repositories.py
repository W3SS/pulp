# -*- coding: utf-8 -*-
#
# Copyright © 2011 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

# Python
import logging

# 3rd Party
import web

# Pulp
from pulp.server.auth.authorization import CREATE, READ, DELETE, EXECUTE, UPDATE
import pulp.server.managers.factory as manager_factory
import pulp.server.managers.repo._exceptions as errors
from pulp.server.webservices.controllers.base import JSONController
from pulp.server.webservices.controllers.decorators import auth_required
from pulp.server.webservices.serialization.error import http_error_obj

# -- constants ----------------------------------------------------------------

_LOG = logging.getLogger(__name__)

# -- repo controllers ---------------------------------------------------------

class RepoCollection(JSONController):

    # Scope: Collection
    # GET:   Retrieve all repositories in the system
    # POST:  Repository Create

    @auth_required(READ)
    def GET(self):
        repo_query_manager = manager_factory.repo_query_manager()
        all_repos = repo_query_manager.find_all()

        # TODO: clean up serialized repos for return

        # Return the repos or an empty list; either way it's a 200
        return self.ok(all_repos)

    @auth_required(CREATE)
    def POST(self):

        # Pull the repo data out of the request body (validation will occur
        # in the manager)
        repo_data = self.params()
        id = repo_data.get('id', None)
        display_name = repo_data.get('display_name', None)
        description = repo_data.get('description', None)
        notes = repo_data.get('notes', None)

        # Creation
        repo_manager = manager_factory.repo_manager()

        try:
            repo = repo_manager.create_repo(id, display_name, description, notes)
            # TODO: explicitly serialize repo for return
            return self.created(None, repo)
        except errors.DuplicateRepoId:
            _LOG.exception('Duplicate repo ID [%s]' % id)
            serialized = http_error_obj(409)
            return self.conflict(serialized)
        except (errors.InvalidRepoId, errors.InvalidRepoMetadata):
            _LOG.exception('Bad request data for repository [%s]' % id)
            serialized = http_error_obj(400)
            return self.bad_request(serialized)

class RepoResource(JSONController):

    # Scope:   Resource
    # GET:     Repository Retrieval
    # DELETE:  Repository Delete
    # PUT:     Repository Update

    @auth_required(READ)
    def GET(self, id):
        query_manager = manager_factory.repo_query_manager()

        repo = query_manager.find_by_id(id)

        if repo is None:
            serialized = http_error_obj(404)
            return self.not_found(serialized)
        else:
            return self.ok(repo)

    @auth_required(DELETE)
    def DELETE(self, id):
        repo_manager = manager_factory.repo_manager()

        try:
            repo_manager.delete_repo(id)
            return self.ok(None)
        except errors.MissingRepo:
            serialized = http_error_obj(404)
            return self.not_found(serialized)

    @auth_required(UPDATE)
    def PUT(self, id):
        parameters = self.params()
        delta = parameters.get('delta', None)

        if delta is None:
            _LOG.exception('Missing delta when updating repository [%s]' % id)
            serialized = http_error_obj(400)
            return self.bad_request(serialized)

        repo_manager = manager_factory.repo_manager()

        try:
            repo = repo_manager.update_repo(id, delta)
            return self.ok(repo)
        except errors.MissingRepo:
            serialized = http_error_obj(404)
            return self.not_found(serialized)
        
# -- importer controllers -----------------------------------------------------

class RepoImporters(JSONController):

    # Scope:  Sub-collection
    # GET:    List Importers
    # POST:   Set Importer

    @auth_required(READ)
    def GET(self, repo_id):
        importer_manager = manager_factory.repo_importer_manager()

        try:
            importers = importer_manager.get_importers(repo_id)
            # TODO: serialize properly
            return self.ok(importers)
        except errors.MissingRepo:
            serialized = http_error_obj(404)
            return self.not_found(serialized)

    @auth_required(CREATE)
    def POST(self, repo_id):

        # Params (validation will occur in the manager)
        params = self.params()
        importer_type = params.get('importer_type_id', None)
        importer_config = params.get('importer_config', None)

        if importer_type is None:
            _LOG.exception('Missing importer type adding importer to repository [%s]' % repo_id)
            serialized = http_error_obj(400)
            return self.bad_request(serialized)

        # Note: If an importer exists, it's removed, so no need to handle 409s.
        # Note: If the plugin raises an exception during initialization, let it
        #  bubble up and be handled like any other 500.

        importer_manager = manager_factory.repo_importer_manager()

        try:
            importer = importer_manager.set_importer(repo_id, importer_type, importer_config)
            # TODO: serialize importer
            return self.created(None, importer)
        except errors.MissingRepo:
            serialized = http_error_obj(404)
            return self.not_found(serialized)
        except (errors.InvalidImporterType, errors.InvalidImporterConfiguration):
            _LOG.exception('Bad request data adding importer of type [%s] to repository [%s]' % (importer_type, repo_id))
            serialized = http_error_obj(400)
            return self.bad_request(serialized)

class RepoImporter(JSONController):

    # Scope:  Exclusive Sub-resource
    # GET:    Get Importer
    # DELETE: Remove Importer
    # PUT:    Update Importer Config

    @auth_required(READ)
    def GET(self, repo_id, importer_id):

        importer_manager = manager_factory.repo_importer_manager()

        try:
            importer = importer_manager.get_importer(repo_id)
            # TODO: serialize properly
            return self.ok(importer)
        except errors.MissingImporter:
            serialized = http_error_obj(404)
            return self.not_found(serialized)

    @auth_required(UPDATE)
    def DELETE(self, repo_id, importer_id):

        importer_manager = manager_factory.repo_importer_manager()

        try:
            importer_manager.remove_importer(repo_id)
            return self.ok(None)
        except (errors.MissingRepo, errors.MissingImporter):
            serialized = http_error_obj(404)
            return self.not_found(serialized)

    @auth_required(UPDATE)
    def PUT(self, repo_id, importer_id):

        # Params (validation will occur in the manager)
        params = self.params()
        importer_config = params.get('importer_config', None)

        if importer_config is None:
            _LOG.exception('Missing configuration updating importer for repository [%s]' % repo_id)
            serialized = http_error_obj(400)
            return self.bad_request(serialized)

        importer_manager = manager_factory.repo_importer_manager()

        try:
            importer = importer_manager.update_importer_config(repo_id, importer_config)
            return self.ok(importer)
        except (errors.MissingRepo, errors.MissingImporter):
            serialized = http_error_obj(404)
            return self.not_found(serialized)

# -- distributor controllers --------------------------------------------------

class RepoDistributors(JSONController):

    # Scope:  Sub-collection
    # GET:    List Distributors
    # POST:   Add Distributor

    @auth_required(READ)
    def GET(self, repo_id):
        distributor_manager = manager_factory.repo_distributor_manager()

        try:
            distributor_list = distributor_manager.get_distributors(repo_id)
            # TODO: serialize each distributor before returning
            return self.ok(distributor_list)
        except errors.MissingRepo:
            serialized = http_error_obj(404)
            return self.not_found(serialized)
    
    @auth_required(CREATE)
    def POST(self, repo_id):

        # Distributor ID is optional and thus isn't part of the URL

        # Params (validation will occur in the manager)
        params = self.params()
        distributor_type = params.get('distributor_type_id', None)
        distributor_config = params.get('distributor_config', None)
        distributor_id = params.get('distributor_id', None)
        auto_publish = params.get('auto_publish', False)

        # Update the repo
        distributor_manager = manager_factory.repo_distributor_manager()

        # Note: The manager will automatically replace a distributor with the
        # same ID, so there is no need to return a 409.

        try:
            added = distributor_manager.add_distributor(repo_id, distributor_type, distributor_config, auto_publish, distributor_id)
            return self.created(None, added)
        except errors.MissingRepo:
            serialized = http_error_obj(404)
            return self.not_found(serialized)
        except (errors.InvalidDistributorId, errors.InvalidDistributorType, errors.InvalidDistributorConfiguration):
            _LOG.exception('Bad request adding distributor of type [%s] to repo [%s]' % (distributor_type, repo_id))
            serialized = http_error_obj(400)
            return self.bad_request(serialized)

class RepoDistributor(JSONController):

    # Scope:  Exclusive Sub-resource
    # GET:    Get Distributor
    # DELETE: Remove Distributor
    # PUT:    Update Distributor Config

    @auth_required(READ)
    def GET(self, repo_id, distributor_id):
        distributor_manager = manager_factory.repo_distributor_manager()

        try:
            distributor = distributor_manager.get_distributor(repo_id, distributor_id)
            # TODO: serialize properly
            return self.ok(distributor)
        except errors.MissingDistributor:
            serialized = http_error_obj(404)
            return self.not_found(serialized)

    @auth_required(UPDATE)
    def DELETE(self, repo_id, distributor_id):
        distributor_manager = manager_factory.repo_distributor_manager()

        try:
            distributor_manager.remove_distributor(repo_id, distributor_id)
            return self.ok(None)
        except (errors.MissingRepo, errors.MissingDistributor):
            serialized = http_error_obj(404)
            return self.not_found(serialized)
        
    @auth_required(UPDATE)
    def PUT(self, repo_id, distributor_id):

        # Params (validation will occur in the manager)
        params = self.params()
        distributor_config = params.get('distributor_config', None)

        if distributor_config is None:
            _LOG.exception('Missing configuration when updating distributor [%s] on repository [%s]' % (distributor_id, repo_id))
            serialized = http_error_obj(400)
            return self.bad_request(serialized)

        distributor_manager = manager_factory.repo_distributor_manager()

        try:
            updated = distributor_manager.update_distributor_config(repo_id, distributor_id, distributor_config)
            return self.ok(updated)
        except (errors.MissingRepo, errors.MissingDistributor):
            serialized = http_error_obj(404)
            return self.not_found(serialized)

# -- history controllers ------------------------------------------------------

class RepoSyncHistory(JSONController):

    # Scope: Resource
    # GET:   Get history entries for the given repo

    @auth_required(READ)
    def GET(self, repo_id):
        # Params
        filters = self.filters(['limit'])
        limit = filters.get('limit', None)

        if limit is not None:
            try:
                limit = int(limit[0])
            except ValueError:
                _LOG.exception('Invalid limit specified [%s]' % limit)
                serialized = http_error_obj(400)
                return self.bad_request(serialized)

        sync_manager = manager_factory.repo_sync_manager()
        try:
            entries = sync_manager.sync_history(repo_id, limit=limit)
            return self.ok(entries)
        except errors.MissingRepo:
            serialized = http_error_obj(404)
            return self.not_found(serialized)

class RepoPublishHistory(JSONController):

    # Scope: Resource
    # GET:   Get history entries for the given repo

    @auth_required(READ)
    def GET(self, repo_id, distributor_id):
        # Params
        filters = self.filters(['limit'])
        limit = filters.get('limit', None)

        if limit is not None:
            try:
                limit = int(limit[0])
            except ValueError:
                _LOG.exception('Invalid limit specified [%s]' % limit)
                serialized = http_error_obj(400)
                return self.bad_request(serialized)

        publish_manager = manager_factory.repo_publish_manager()
        try:
            entries = publish_manager.publish_history(repo_id, distributor_id, limit=limit)
            return self.ok(entries)
        except (errors.MissingRepo, errors.MissingDistributor):
            serialized = http_error_obj(404)
            return self.not_found(serialized)

# -- action controllers -------------------------------------------------------

class RepoSync(JSONController):

    # Scope: Action
    # POST:  Trigger a repo sync

    @auth_required(EXECUTE)
    def POST(self, repo_id):

        # TODO: Add timeout support

        # Params
        params = self.params()
        overrides = params.get('override_config', None)

        # Trigger the sync
        # TODO: Make this run asynchronously
        repo_sync_manager = manager_factory.repo_sync_manager()
        repo_sync_manager.sync(repo_id, overrides)

        return self.ok(True)

class RepoPublish(JSONController):

    # Scope: Action
    # POST:  Trigger a repo publish

    @auth_required(EXECUTE)
    def POST(self, repo_id):

        # TODO: Add timeout support

        # Params
        params = self.params()
        distributor_id = params.get('id', None)
        overrides = params.get('override_config', None)

        # Trigger the publish
        # TODO: Make this run asynchronously
        repo_publish_manager = manager_factory.repo_publish_manager()
        repo_publish_manager.publish(repo_id, distributor_id, overrides)
        
        return self.ok(True)

# -- web.py application -------------------------------------------------------

# These are defined under /v2/repositories/ (see application.py to double-check)
urls = (
    '/', 'RepoCollection', # collection
    '/([^/]+)/$', 'RepoResource', # resourcce

    '/([^/]+)/importers/$', 'RepoImporters', # sub-collection
    '/([^/]+)/importers/([^/]+)/$', 'RepoImporter', # exclusive sub-resource

    '/([^/]+)/distributors/$', 'RepoDistributors', # sub-collection
    '/([^/]+)/distributors/([^/]+)/$', 'RepoDistributor', # exclusive sub-resource

    '/([^/]+)/sync_history/$', 'RepoSyncHistory', # sub-collection
    '/([^/]+)/publish_history/([^/]+)/$', 'RepoPublishHistory', # sub-collection

    '/([^/]+)/actions/sync/$', 'RepoSync', # sub-resource action
    '/([^/]+)/actions/publish/$', 'RepoPublish', # sub-resource action
)

application = web.application(urls, globals())
