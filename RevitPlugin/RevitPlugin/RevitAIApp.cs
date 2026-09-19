using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using Npgsql;

namespace RevitPlugin
{
    public class RevitAIApp : IExternalApplication
    {
        private static ExternalEvent externalEvent;
        private static RevitAIExternalEventHandler externalEventHandler;
        private static Thread httpServerThread;
        private static HttpListener httpListener;
        private static bool serverRunning = false;

        private const string ServerUrl =
            "http://127.0.0.1:8765/";

        private const string DebugFile =
            @"C:\Users\Hemkumar Ramesh\Documents\RevitAI\revit-debug.txt";

        public Result OnStartup(
            UIControlledApplication application)
        {
            try
            {
                Log("========================================");
                Log("RevitAI OnStartup started");
                Log("========================================");

                externalEventHandler =
                    new RevitAIExternalEventHandler();

                externalEvent =
                    ExternalEvent.Create(
                        externalEventHandler);

                Log("ExternalEvent created successfully");

                CreateRibbon(application);

                StartHttpServer();

                Log("RevitAI OnStartup completed successfully");

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                Log("OnStartup ERROR: " + ex);

                TaskDialog.Show(
                    "RevitAI Error",
                    "Failed to start RevitAI:\n\n" +
                    ex.Message);

                return Result.Failed;
            }
        }

        public Result OnShutdown(
            UIControlledApplication application)
        {
            try
            {
                Log("RevitAI shutdown started");

                serverRunning = false;

                try
                {
                    if (httpListener != null)
                    {
                        Log("Stopping HTTP listener during RevitAI shutdown");

                        httpListener.Stop();
                        httpListener.Close();
                        httpListener = null;
                    }
                }
                catch (Exception ex)
                {
                    Log("HTTP listener shutdown ERROR: " + ex);
                }

                if (httpServerThread != null &&
                    httpServerThread.IsAlive)
                {
                    try
                    {
                        httpServerThread.Join(2000);
                    }
                    catch
                    {
                    }
                }

                httpServerThread = null;

                Log("RevitAI shutdown completed");

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                Log("OnShutdown ERROR: " + ex);

                return Result.Failed;
            }
        }

        private void CreateRibbon(
            UIControlledApplication application)
        {
            string tabName = "RevitAI";
            string panelName = "AI Assistant";

            try
            {
                application.CreateRibbonTab(tabName);
            }
            catch
            {
                // Tab may already exist.
            }

            RibbonPanel panel;

            try
            {
                panel =
                    application.CreateRibbonPanel(
                        tabName,
                        panelName);
            }
            catch
            {
                panel = null;
            }

            if (panel == null)
            {
                Log("Could not create ribbon panel");

                return;
            }

            // ====================================================
            // RevitAI Button
            // ====================================================

            PushButtonData buttonData =
                new PushButtonData(
                    "RevitAIButton",
                    "RevitAI",
                    typeof(RevitAIApp).Assembly.Location,
                    "RevitPlugin.RevitAICommand");

            PushButton button =
                panel.AddItem(buttonData)
                as PushButton;

            if (button != null)
            {
                button.ToolTip =
                    "Open RevitAI Assistant";

                Log("RevitAI ribbon button created");
            }

            // ====================================================
            // Sync Views Button
            // ====================================================

            PushButtonData syncButtonData =
                new PushButtonData(
                    "SyncViewsButton",
                    "Sync Views",
                    typeof(RevitAIApp).Assembly.Location,
                    "RevitPlugin.SyncViewsCommand");

            PushButton syncButton =
                panel.AddItem(syncButtonData)
                as PushButton;

            if (syncButton != null)
            {
                syncButton.ToolTip =
                    "Sync Revit views to the RevitAI PostgreSQL database";

                Log("Sync Views ribbon button created");
            }
        }

        private void StartHttpServer()
        {
            if (serverRunning)
            {
                Log("HTTP server is already running");

                return;
            }

            serverRunning = true;

            httpServerThread =
                new Thread(
                    HttpServerLoop);

            httpServerThread.IsBackground = true;

            httpServerThread.Start();

            Log(
                "HTTP server thread started on " +
                ServerUrl);
        }

        private void HttpServerLoop()
        {
            HttpListener listener =
                new HttpListener();

            try
            {
                httpListener = listener;

                listener.Prefixes.Add(ServerUrl);

                listener.Start();

                Log(
                    "HTTP server listening on " +
                    ServerUrl);

                while (serverRunning)
                {
                    try
                    {
                        HttpListenerContext context =
                            listener.GetContext();

                        ThreadPool.QueueUserWorkItem(
                            _ =>
                            {
                                HandleRequest(
                                    context);
                            });
                    }
                    catch (HttpListenerException ex)
                    {
                        if (!serverRunning)
                        {
                            break;
                        }

                        Log(
                            "HTTP listener loop ERROR: " +
                            ex);
                    }
                    catch (ObjectDisposedException)
                    {
                        if (!serverRunning)
                        {
                            break;
                        }

                        Log(
                            "HTTP listener disposed unexpectedly.");
                    }
                    catch (Exception ex)
                    {
                        Log(
                            "HTTP listener loop ERROR: " +
                            ex);
                    }
                }
            }
            catch (Exception ex)
            {
                Log(
                    "HTTP server startup ERROR: " +
                    ex);
            }
            finally
            {
                try
                {
                    listener.Stop();
                    listener.Close();
                }
                catch
                {
                }

                if (ReferenceEquals(httpListener, listener))
                {
                    httpListener = null;
                }

                Log("HTTP server stopped");
            }
        }

        private void HandleRequest(
            HttpListenerContext context)
        {
            try
            {
                Log("----------------------------------------");
                Log("HTTP request received");

                string requestBody;

                using (
                    StreamReader reader =
                        new StreamReader(
                            context.Request.InputStream,
                            context.Request.ContentEncoding))
                {
                    requestBody =
                        reader.ReadToEnd();
                }

                Log(
                    "Request body: " +
                    requestBody);

                string requestPath =
                    context.Request.Url.AbsolutePath;

                // ============================================================
                // GET /current-project
                // ============================================================
                if (
                    context.Request.HttpMethod.Equals(
                        "GET",
                        StringComparison.OrdinalIgnoreCase)
                    &&
                    string.Equals(
                        requestPath,
                        "/current-project",
                        StringComparison.OrdinalIgnoreCase))
                {
                    string currentProjectRequest =
                        "{\"action\":\"get_current_project\"}";

                    using (
                        ManualResetEventSlim completionEvent =
                            new ManualResetEventSlim(false))
                    {
                        externalEventHandler.SetRequest(
                            currentProjectRequest,
                            completionEvent);

                        ExternalEventRequest requestResult =
                            externalEvent.Raise();

                        Log(
                            "Current project ExternalEvent Raise result: " +
                            requestResult.ToString());

                        bool completed =
                            completionEvent.Wait(
                                TimeSpan.FromSeconds(10));

                        if (!completed)
                        {
                            Log(
                                "Current project request timed out.");

                            SendHttpResponse(
                                context,
                                504,
                                "application/json",
                                "{\"success\":false,\"message\":\"Timed out while reading the active Revit project.\"}");

                            return;
                        }

                        string projectResponse =
                            externalEventHandler.GetResponse();

                        if (string.IsNullOrWhiteSpace(projectResponse))
                        {
                            projectResponse =
                                "{\"success\":false,\"message\":\"Revit did not return project information.\"}";
                        }

                        SendHttpResponse(
                            context,
                            200,
                            "application/json",
                            projectResponse);

                        Log(
                            "Current project response sent successfully");

                        return;
                    }
                }

                // ============================================================
                // POST / (Action Requests, e.g. OPEN view)
                // Wait synchronously for Revit ExternalEvent to finish
                // and return structured JSON response to Electron.
                // ============================================================

                using (
                    ManualResetEventSlim completionEvent =
                        new ManualResetEventSlim(false))
                {
                    externalEventHandler.SetRequest(
                        requestBody,
                        completionEvent);

                    Log(
                        "Request stored in ExternalEventHandler");

                    ExternalEventRequest normalRequestResult =
                        externalEvent.Raise();

                    Log(
                        "ExternalEvent Raise result: " +
                        normalRequestResult.ToString());

                    bool completed =
                        completionEvent.Wait(
                            TimeSpan.FromSeconds(10));

                    if (!completed)
                    {
                        Log(
                            "Revit action request timed out.");

                        SendHttpResponse(
                            context,
                            504,
                            "application/json",
                            "{\"success\":false,\"message\":\"Timed out while executing the Revit action.\"}");

                        return;
                    }

                    string actionResponse =
                        externalEventHandler.GetResponse();

                    if (string.IsNullOrWhiteSpace(actionResponse))
                    {
                        actionResponse =
                            "{\"success\":true,\"message\":\"Request processed by RevitAI.\"}";
                    }

                    SendHttpResponse(
                        context,
                        200,
                        "application/json",
                        actionResponse);

                    Log(
                        "HTTP response sent successfully: " + actionResponse);
                }
            }
            catch (Exception ex)
            {
                Log(
                    "HandleRequest ERROR: " +
                    ex);

                try
                {
                    SendHttpResponse(
                        context,
                        500,
                        "application/json",
                        "{\"success\":false,\"message\":\"Error: " +
                        JsonEscape(ex.Message) +
                        "\"}");
                }
                catch
                {
                }
            }
        }

        private void SendHttpResponse(
            HttpListenerContext context,
            int statusCode,
            string contentType,
            string responseText)
        {
            byte[] responseBytes =
                Encoding.UTF8.GetBytes(
                    responseText ?? "");

            context.Response.StatusCode =
                statusCode;

            context.Response.ContentType =
                contentType;

            context.Response.ContentEncoding =
                Encoding.UTF8;

            context.Response.ContentLength64 =
                responseBytes.Length;

            context.Response.OutputStream.Write(
                responseBytes,
                0,
                responseBytes.Length);

            context.Response.OutputStream.Close();
        }

        public static string NormalizeFilePath(
            string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return null;
            }

            try
            {
                string trimmed = path.Trim();
                string fullPath = Path.GetFullPath(trimmed);
                return fullPath.ToLowerInvariant().Replace('/', '\\');
            }
            catch
            {
                return path.Trim().ToLowerInvariant().Replace('/', '\\');
            }
        }

        public static string JsonEscape(
            string value)
        {
            if (value == null)
            {
                return "";
            }

            return value
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\r", "\\r")
                .Replace("\n", "\\n")
                .Replace("\t", "\\t");
        }

        public static void Log(
            string message)
        {
            try
            {
                string directory =
                    Path.GetDirectoryName(
                        DebugFile);

                if (!Directory.Exists(directory))
                {
                    Directory.CreateDirectory(
                        directory);
                }

                File.AppendAllText(
                    DebugFile,
                    DateTime.Now.ToString(
                        "dd-MM-yyyy HH:mm:ss")
                    + " | "
                    + message
                    + Environment.NewLine);
            }
            catch
            {
            }
        }
    }

    // ============================================================
    // External Event Handler
    // ============================================================

    public class RevitAIExternalEventHandler :
        IExternalEventHandler
    {
        private string pendingRequest;
        private string pendingResponse;

        private ManualResetEventSlim pendingCompletionEvent;

        private readonly object requestLock =
            new object();

        public void SetRequest(
            string request)
        {
            SetRequest(
                request,
                null);
        }

        public void SetRequest(
            string request,
            ManualResetEventSlim completionEvent)
        {
            lock (requestLock)
            {
                pendingRequest = request;
                pendingResponse = null;
                pendingCompletionEvent = completionEvent;
            }

            RevitAIApp.Log(
                "SetRequest called");
        }

        public string GetResponse()
        {
            lock (requestLock)
            {
                return pendingResponse;
            }
        }

        public void Execute(
            UIApplication app)
        {
            try
            {
                string request;

                lock (requestLock)
                {
                    request = pendingRequest;

                    pendingRequest = null;
                }

                if (string.IsNullOrWhiteSpace(request))
                {
                    RevitAIApp.Log(
                        "Execute called but no pending request exists");

                    return;
                }

                RevitAIApp.Log(
                    "Execute() called | Request: " +
                    request);

                string action =
                    ExtractJsonValue(
                        request,
                        "action");

                string name =
                    ExtractJsonValue(
                        request,
                        "name");

                string type =
                    ExtractJsonValue(
                        request,
                        "type");

                string description =
                    ExtractJsonValue(
                        request,
                        "description");

                long? revitViewId =
                    ExtractJsonLongValue(
                        request,
                        "revit_view_id");

                long? revitElementId =
                    ExtractJsonLongValue(
                        request,
                        "revit_element_id");

                int? projectId =
                    (int?)ExtractJsonLongValue(
                        request,
                        "project_id");

                RevitAIApp.Log(
                    "Parsed request | " +
                    "Action: " +
                    action +
                    " | View: " +
                    name +
                    " | Type: " +
                    type +
                    " | RevitViewId: " +
                    (revitViewId?.ToString() ?? "null") +
                    " | RevitElementId: " +
                    (revitElementId?.ToString() ?? "null") +
                    " | ProjectId: " +
                    (projectId?.ToString() ?? "null"));

                // ============================================================
                // CURRENT PROJECT REQUEST
                // ============================================================

                if (
                    string.Equals(
                        action,
                        "get_current_project",
                        StringComparison.OrdinalIgnoreCase))
                {
                    string response =
                        GetCurrentProject(app);

                    lock (requestLock)
                    {
                        pendingResponse = response;
                    }

                    SignalCompletion();

                    return;
                }

                // ============================================================
                // SYNC VIEWS REQUEST
                // ============================================================

                if (
                    string.Equals(
                        action,
                        "sync",
                        StringComparison.OrdinalIgnoreCase)
                    ||
                    string.Equals(
                        action,
                        "sync_views",
                        StringComparison.OrdinalIgnoreCase))
                {
                    string syncResponse =
                        SyncProjectViews(app);

                    lock (requestLock)
                    {
                        pendingResponse = syncResponse;
                    }

                    SignalCompletion();

                    return;
                }

                // ============================================================
                // OPEN VIEW / SELECT / HIGHLIGHT / ZOOM ACTIONS
                // ============================================================

                if (
                    string.Equals(
                        action,
                        "open",
                        StringComparison.OrdinalIgnoreCase))
                {
                    if (IsViewResultType(type))
                    {
                        string openResponse =
                            OpenView(
                                app,
                                name,
                                revitViewId,
                                projectId);

                        lock (requestLock)
                        {
                            pendingResponse = openResponse;
                        }

                        SignalCompletion();

                        return;
                    }
                    else
                    {
                        string errResp =
                            "{\"success\":false,\"message\":\"Unsupported result type: " +
                            RevitAIApp.JsonEscape(type) + "\",\"error_code\":\"UNSUPPORTED_TYPE\"}";

                        lock (requestLock)
                        {
                            pendingResponse = errResp;
                        }

                        SignalCompletion();

                        RevitAIApp.Log("Unsupported result type: " + type);

                        TaskDialog.Show(
                            "RevitAI",
                            "Unsupported result type:\n\n" +
                            type);

                        return;
                    }
                }
                else if (
                    string.Equals(action, "select", StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(action, "highlight", StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(action, "zoom", StringComparison.OrdinalIgnoreCase))
                {
                    string elemResponse =
                        SelectOrZoomElement(
                            app,
                            action,
                            revitElementId ?? revitViewId,
                            projectId);

                    lock (requestLock)
                    {
                        pendingResponse = elemResponse;
                    }

                    SignalCompletion();

                    return;
                }
                else
                {
                    string errResp =
                        "{\"success\":false,\"message\":\"Unsupported action: " +
                        RevitAIApp.JsonEscape(action) + "\",\"error_code\":\"UNSUPPORTED_ACTION\"}";

                    lock (requestLock)
                    {
                        pendingResponse = errResp;
                    }

                    SignalCompletion();

                    RevitAIApp.Log("[Action] Unsupported action: " + action);

                    return;
                }
            }
            catch (Exception ex)
            {
                lock (requestLock)
                {
                    pendingResponse =
                        "{"
                        + "\"success\":false,"
                        + "\"message\":\""
                        + RevitAIApp.JsonEscape(
                            ex.Message)
                        + "\""
                        + "}";
                }

                SignalCompletion();

                RevitAIApp.Log(
                    "Execute ERROR: " +
                    ex);

                TaskDialog.Show(
                    "RevitAI Execute Error",
                    ex.ToString());
            }
        }

        private void SignalCompletion()
        {
            ManualResetEventSlim completionEvent;

            lock (requestLock)
            {
                completionEvent =
                    pendingCompletionEvent;

                pendingCompletionEvent =
                    null;
            }

            if (completionEvent != null)
            {
                try
                {
                    completionEvent.Set();
                }
                catch
                {
                }
            }
        }

        private string GetCurrentProject(
            UIApplication app)
        {
            try
            {
                UIDocument uidoc =
                    app.ActiveUIDocument;

                if (uidoc == null)
                {
                    return
                        "{\"success\":false,\"message\":\"No active Revit document was found.\"}";
                }

                Document doc =
                    uidoc.Document;

                if (doc == null)
                {
                    return
                        "{\"success\":false,\"message\":\"No active Revit document was found.\"}";
                }

                string projectName =
                    doc.Title;

                string rawFilePath =
                    doc.PathName;

                string normalizedPath =
                    RevitAIApp.NormalizeFilePath(rawFilePath);

                int? projectId =
                    FindProjectId(
                        projectName,
                        normalizedPath);

                bool isSynced = false;

                if (projectId.HasValue)
                {
                    isSynced = IsProjectSyncedInDatabase(projectId.Value);
                }

                // ============================================================
                // AUTOMATIC PROJECT SYNCHRONIZATION REQUIREMENT
                // If project is not in database or has no views synchronized,
                // automatically synchronize its Revit data now.
                // ============================================================
                if (!projectId.HasValue || !isSynced)
                {
                    RevitAIApp.Log(
                        "Active document '" + projectName + "' is not synchronized. " +
                        "Performing automatic project synchronization...");

                    SyncProjectViews(app);

                    projectId =
                        FindProjectId(
                            projectName,
                            normalizedPath);

                    if (projectId.HasValue)
                    {
                        isSynced = IsProjectSyncedInDatabase(projectId.Value);
                    }
                }

                string projectIdJson =
                    (projectId.HasValue && isSynced)
                        ? projectId.Value.ToString()
                        : "null";

                string filePathJson =
                    normalizedPath == null
                        ? "null"
                        : "\"" +
                          RevitAIApp.JsonEscape(normalizedPath) +
                          "\"";

                string message =
                    (projectId.HasValue && isSynced)
                        ? "Active Revit project found."
                        : "Active Revit project is not synchronized yet.";

                return
                    "{"
                    + "\"success\":true,"
                    + "\"synced\":" +
                    (isSynced ? "true" : "false") +
                    ","
                    + "\"project_id\":" +
                    projectIdJson +
                    ","
                    + "\"project_name\":\"" +
                    RevitAIApp.JsonEscape(projectName) +
                    "\","
                    + "\"file_path\":" +
                    filePathJson +
                    ","
                    + "\"message\":\"" +
                    RevitAIApp.JsonEscape(message) +
                    "\""
                    + "}";
            }
            catch (Exception ex)
            {
                RevitAIApp.Log(
                    "GetCurrentProject ERROR: " +
                    ex);

                return
                    "{"
                    + "\"success\":false,\"message\":\"" +
                    RevitAIApp.JsonEscape(
                        ex.Message) +
                    "\""
                    + "}";
            }
        }

        public static bool IsProjectSyncedInDatabase(
            int projectId)
        {
            try
            {
                using (
                    NpgsqlConnection connection =
                        new NpgsqlConnection(
                            PostgreSQLConfig.ConnectionString))
                {
                    connection.Open();
                    using (
                        NpgsqlCommand command =
                            new NpgsqlCommand(
                                @"SELECT COUNT(*)
                                  FROM revit_views
                                  WHERE project_id = @project_id;",
                                connection))
                    {
                        command.Parameters.AddWithValue(
                            "project_id",
                            projectId);

                        object result = command.ExecuteScalar();
                        if (result != null && result != DBNull.Value)
                        {
                            long count = Convert.ToInt64(result);
                            return count > 0;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                RevitAIApp.Log("IsProjectSyncedInDatabase ERROR: " + ex);
            }
            return false;
        }

        public static string SyncProjectViews(
            UIApplication app)
        {
            try
            {
                RevitAIApp.Log("========================================");
                RevitAIApp.Log("SyncProjectViews started");

                UIDocument uidoc = app.ActiveUIDocument;

                if (uidoc == null)
                {
                    return "{\"success\":false,\"message\":\"No active Revit document was found.\"}";
                }

                Document doc = uidoc.Document;

                if (doc == null)
                {
                    return "{\"success\":false,\"message\":\"No active Revit document was found.\"}";
                }

                string projectName = doc.Title;
                string rawFilePath = doc.PathName;
                string normalizedPath = RevitAIApp.NormalizeFilePath(rawFilePath);

                RevitAIApp.Log("Syncing document: " + projectName);
                RevitAIApp.Log("Normalized path: " + (normalizedPath ?? "[UNSAVED PROJECT]"));

                FilteredElementCollector collector =
                    new FilteredElementCollector(doc).OfClass(typeof(View));

                int viewCount = 0;
                int projectId = 0;

                using (
                    NpgsqlConnection connection =
                        new NpgsqlConnection(PostgreSQLConfig.ConnectionString))
                {
                    connection.Open();

                    using (
                        NpgsqlTransaction transaction =
                            connection.BeginTransaction())
                    {
                        try
                        {
                            projectId =
                                GetOrCreateProject(
                                    connection,
                                    transaction,
                                    projectName,
                                    normalizedPath);

                            RevitAIApp.Log("Project ID resolved: " + projectId);

                            // ====================================================
                            // PROJECT-SCOPED SYNCHRONIZATION:
                            // DELETE ONLY THIS PROJECT'S EXISTING VIEWS
                            // ====================================================
                            using (
                                NpgsqlCommand deleteCommand =
                                    new NpgsqlCommand(
                                        @"DELETE FROM revit_views
                                          WHERE project_id = @project_id;",
                                        connection,
                                        transaction))
                            {
                                deleteCommand.Parameters.AddWithValue("project_id", projectId);
                                int deletedRows = deleteCommand.ExecuteNonQuery();
                                RevitAIApp.Log("Deleted old views for project " + projectId + ": " + deletedRows);
                            }

                            foreach (Element element in collector)
                            {
                                View view = element as View;
                                if (view == null || view.IsTemplate)
                                {
                                    continue;
                                }

                                string viewType = view.ViewType.ToString();
                                string viewName = view.Name;

                                Autodesk.Revit.DB.ViewSheet sheet = view as Autodesk.Revit.DB.ViewSheet;
                                if (sheet != null)
                                {
                                    viewType = "DrawingSheet";
                                    if (!string.IsNullOrEmpty(sheet.SheetNumber) && !viewName.StartsWith(sheet.SheetNumber))
                                    {
                                        viewName = sheet.SheetNumber + " - " + sheet.Name;
                                    }
                                }

                                string description = BuildViewDescription(view);
                                string levelName = GetViewLevelName(view);

                                using (
                                    NpgsqlCommand insertCommand =
                                        new NpgsqlCommand(
                                            @"INSERT INTO revit_views
                                              (revit_view_id, name, view_type, description, level_name, project_id)
                                              VALUES
                                              (@revit_view_id, @name, @view_type, @description, @level_name, @project_id);",
                                            connection,
                                            transaction))
                                {
                                    insertCommand.Parameters.AddWithValue("revit_view_id", view.Id.Value);
                                    insertCommand.Parameters.AddWithValue("name", viewName);
                                    insertCommand.Parameters.AddWithValue("view_type", viewType);
                                    insertCommand.Parameters.AddWithValue("description", description);
                                    insertCommand.Parameters.AddWithValue("level_name", (object)levelName ?? DBNull.Value);
                                    insertCommand.Parameters.AddWithValue("project_id", projectId);

                                    insertCommand.ExecuteNonQuery();
                                }

                                viewCount++;
                            }

                            // Optional Element Sync
                            try
                            {
                                using (NpgsqlCommand createElemTableCmd = new NpgsqlCommand(
                                    @"CREATE TABLE IF NOT EXISTS revit_elements (
                                        id SERIAL PRIMARY KEY,
                                        project_id INTEGER NOT NULL REFERENCES revit_projects(id) ON DELETE CASCADE,
                                        revit_element_id BIGINT NOT NULL,
                                        category VARCHAR(100) NOT NULL,
                                        family_name VARCHAR(255),
                                        type_name VARCHAR(255),
                                        name VARCHAR(255),
                                        level_name VARCHAR(100),
                                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                    );", connection, transaction))
                                {
                                    createElemTableCmd.ExecuteNonQuery();
                                }

                                using (NpgsqlCommand deleteElemCmd = new NpgsqlCommand(
                                    @"DELETE FROM revit_elements WHERE project_id = @project_id;", connection, transaction))
                                {
                                    deleteElemCmd.Parameters.AddWithValue("project_id", projectId);
                                    deleteElemCmd.ExecuteNonQuery();
                                }

                                System.Collections.Generic.List<BuiltInCategory> categoriesToSync = new System.Collections.Generic.List<BuiltInCategory>
                                {
                                    BuiltInCategory.OST_Walls,
                                    BuiltInCategory.OST_Doors,
                                    BuiltInCategory.OST_Windows,
                                    BuiltInCategory.OST_Rooms,
                                    BuiltInCategory.OST_Floors,
                                    BuiltInCategory.OST_Ceilings,
                                    BuiltInCategory.OST_Columns,
                                    BuiltInCategory.OST_StructuralColumns,
                                    BuiltInCategory.OST_StructuralFraming,
                                    BuiltInCategory.OST_StructuralFoundation
                                };

                                ElementMulticategoryFilter catFilter = new ElementMulticategoryFilter(categoriesToSync);
                                FilteredElementCollector elemCollector = new FilteredElementCollector(doc).WherePasses(catFilter).WhereElementIsNotElementType();

                                foreach (Element elem in elemCollector)
                                {
                                    string category = elem.Category != null ? elem.Category.Name : "Element";
                                    string familyName = "";
                                    string typeName = elem.Name;
                                    ElementType elemType = doc.GetElement(elem.GetTypeId()) as ElementType;
                                    if (elemType != null)
                                    {
                                        familyName = elemType.FamilyName;
                                        typeName = elemType.Name;
                                    }
                                    string elemName = elem.Name;
                                    string elemLevelName = GetViewLevelName(doc.GetElement(elem.LevelId) as View) ?? "";

                                    using (NpgsqlCommand insertElemCmd = new NpgsqlCommand(
                                        @"INSERT INTO revit_elements (revit_element_id, category, family_name, type_name, name, level_name, project_id)
                                          VALUES (@revit_element_id, @category, @family_name, @type_name, @name, @level_name, @project_id);",
                                        connection, transaction))
                                    {
                                        insertElemCmd.Parameters.AddWithValue("revit_element_id", elem.Id.Value);
                                        insertElemCmd.Parameters.AddWithValue("category", category);
                                        insertElemCmd.Parameters.AddWithValue("family_name", (object)familyName ?? DBNull.Value);
                                        insertElemCmd.Parameters.AddWithValue("type_name", (object)typeName ?? DBNull.Value);
                                        insertElemCmd.Parameters.AddWithValue("name", (object)elemName ?? DBNull.Value);
                                        insertElemCmd.Parameters.AddWithValue("level_name", (object)elemLevelName ?? DBNull.Value);
                                        insertElemCmd.Parameters.AddWithValue("project_id", projectId);
                                        insertElemCmd.ExecuteNonQuery();
                                    }
                                }
                            }
                            catch (Exception elemEx)
                            {
                                RevitAIApp.Log("Element sync warning: " + elemEx.Message);
                            }

                            transaction.Commit();
                            RevitAIApp.Log("PostgreSQL transaction committed");
                        }
                        catch
                        {
                            transaction.Rollback();
                            RevitAIApp.Log("PostgreSQL transaction rolled back");
                            throw;
                        }
                    }

                    connection.Close();
                }

                RevitAIApp.Log("Total views synchronized: " + viewCount);

                return
                    "{"
                    + "\"success\":true,"
                    + "\"project_id\":" + projectId + ","
                    + "\"project_name\":\"" + RevitAIApp.JsonEscape(projectName) + "\","
                    + "\"views_count\":" + viewCount + ","
                    + "\"message\":\"Project synchronization completed successfully.\""
                    + "}";
            }
            catch (Exception ex)
            {
                RevitAIApp.Log("SyncProjectViews ERROR: " + ex);
                return "{\"success\":false,\"message\":\"Sync failed: " + RevitAIApp.JsonEscape(ex.Message) + "\"}";
            }
        }

        public static int GetOrCreateProject(
            NpgsqlConnection connection,
            NpgsqlTransaction transaction,
            string projectName,
            string normalizedFilePath)
        {
            int? existingId = FindProjectId(projectName, normalizedFilePath);
            if (existingId.HasValue)
            {
                return existingId.Value;
            }

            using (
                NpgsqlCommand command =
                    new NpgsqlCommand(
                        @"INSERT INTO revit_projects (project_name, file_path)
                          VALUES (@project_name, @file_path)
                          RETURNING id;",
                        connection,
                        transaction))
            {
                command.Parameters.AddWithValue("project_name", projectName);
                command.Parameters.AddWithValue("file_path", (object)normalizedFilePath ?? DBNull.Value);

                object result = command.ExecuteScalar();
                if (result != null && result != DBNull.Value)
                {
                    return Convert.ToInt32(result);
                }
            }

            throw new Exception("Failed to get or create project in database.");
        }

        public static string BuildViewDescription(View view)
        {
            try
            {
                string type =
                    view.ViewType.ToString();

                string levelName =
                    GetViewLevelName(view);

                if (
                    string.Equals(
                        type,
                        "FloorPlan",
                        StringComparison.OrdinalIgnoreCase))
                {
                    if (!string.IsNullOrWhiteSpace(levelName))
                    {
                        return
                            "Floor plan view: " +
                            view.Name +
                            ". Level: " +
                            levelName +
                            ". Floor plan for level " +
                            levelName + ".";
                    }

                    return
                        "Floor plan view: " +
                        view.Name;
                }

                if (
                    string.Equals(
                        type,
                        "CeilingPlan",
                        StringComparison.OrdinalIgnoreCase))
                {
                    if (!string.IsNullOrWhiteSpace(levelName))
                    {
                        return
                            "Ceiling plan view: " +
                            view.Name +
                            ". Level: " +
                            levelName +
                            ". Ceiling plan for level " +
                            levelName + ".";
                    }

                    return
                        "Ceiling plan view: " +
                        view.Name;
                }

                if (
                    string.Equals(
                        type,
                        "Elevation",
                        StringComparison.OrdinalIgnoreCase))
                {
                    return
                        "Elevation view: " +
                        view.Name;
                }

                if (
                    string.Equals(
                        type,
                        "Section",
                        StringComparison.OrdinalIgnoreCase))
                {
                    return
                        "Section view: " +
                        view.Name;
                }

                if (
                    string.Equals(
                        type,
                        "ThreeD",
                        StringComparison.OrdinalIgnoreCase))
                {
                    return
                        "3D view: " +
                        view.Name;
                }

                if (
                    string.Equals(
                        type,
                        "DraftingView",
                        StringComparison.OrdinalIgnoreCase))
                {
                    return
                        "Drafting view: " +
                        view.Name;
                }

                if (
                    string.Equals(
                        type,
                        "Schedule",
                        StringComparison.OrdinalIgnoreCase))
                {
                    return
                        "Schedule view: " +
                        view.Name;
                }

                if (
                    string.Equals(
                        type,
                        "DrawingSheet",
                        StringComparison.OrdinalIgnoreCase))
                {
                    return
                        "Drawing sheet: " +
                        view.Name;
                }

                return
                    type +
                    " view: " +
                    view.Name;
            }
            catch
            {
                return
                    "Revit view: " +
                    view.Name;
            }
        }

        public static string GetViewLevelName(View view)
        {
            try
            {
                ViewPlan viewPlan = view as ViewPlan;
                if (viewPlan != null && viewPlan.GenLevel != null)
                {
                    return viewPlan.GenLevel.Name;
                }
                return null;
            }
            catch
            {
                return null;
            }
        }

        public static int? FindProjectId(
            string projectName,
            string normalizedFilePath)
        {
            try
            {
                using (
                    NpgsqlConnection connection =
                        new NpgsqlConnection(
                            PostgreSQLConfig.ConnectionString))
                {
                    connection.Open();

                    // --------------------------------------------------------
                    // Saved Revit document:
                    // file path is the primary project identity.
                    // --------------------------------------------------------

                    if (!string.IsNullOrWhiteSpace(normalizedFilePath))
                    {
                        using (
                            NpgsqlCommand command =
                                new NpgsqlCommand(
                                    @"SELECT id
                                      FROM revit_projects
                                      WHERE file_path IS NOT NULL
                                        AND (file_path = @file_path OR LOWER(REPLACE(file_path, '/', '\')) = @file_path)
                                      ORDER BY id
                                      LIMIT 1;",
                                    connection))
                        {
                            command.Parameters.AddWithValue(
                                "file_path",
                                normalizedFilePath);

                            object result =
                                command.ExecuteScalar();

                            if (
                                result != null
                                &&
                                result != DBNull.Value)
                            {
                                return Convert.ToInt32(
                                    result);
                            }
                        }
                    }

                    // --------------------------------------------------------
                    // Unsaved Revit document:
                    // fall back to project name when file_path IS NULL.
                    // --------------------------------------------------------

                    if (string.IsNullOrWhiteSpace(normalizedFilePath))
                    {
                        using (
                            NpgsqlCommand command =
                                new NpgsqlCommand(
                                    @"SELECT id
                                      FROM revit_projects
                                      WHERE project_name = @project_name
                                        AND file_path IS NULL
                                      ORDER BY id
                                      LIMIT 1;",
                                    connection))
                        {
                            command.Parameters.AddWithValue(
                                "project_name",
                                projectName);

                            object result =
                                command.ExecuteScalar();

                            if (
                                result != null
                                &&
                                result != DBNull.Value)
                            {
                                return Convert.ToInt32(
                                    result);
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                RevitAIApp.Log(
                    "FindProjectId ERROR: " +
                    ex);
            }

            return null;
        }

        private bool IsViewResultType(
            string type)
        {
            if (string.IsNullOrWhiteSpace(type))
            {
                return false;
            }

            if (string.Equals(
                    type,
                    "view",
                    StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            string[] supportedViewTypes =
            {
                "FloorPlan",
                "CeilingPlan",
                "AreaPlan",
                "Section",
                "Elevation",
                "ThreeD",
                "DrawingSheet",
                "Schedule",
                "Detail",
                "DraftingView",
                "Legend",
                "EngineeringPlan",
                "Walkthrough",
                "SystemBrowser",
                "Internal"
            };

            foreach (string viewType in supportedViewTypes)
            {
                if (string.Equals(
                        type,
                        viewType,
                        StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            return false;
        }

        private string SelectOrZoomElement(
            UIApplication app,
            string actionName,
            long? elementIdVal,
            int? targetProjectId)
        {
            try
            {
                string normAction = actionName?.Trim().ToUpperInvariant() ?? "SELECT";
                RevitAIApp.Log(
                    "[Action] Received: action=" + normAction +
                    " project_id=" + (targetProjectId?.ToString() ?? "null") +
                    " revit_element_id=" + (elementIdVal?.ToString() ?? "null"));

                UIDocument uidoc = app.ActiveUIDocument;
                if (uidoc == null || uidoc.Document == null)
                {
                    RevitAIApp.Log("[Action] Error: NO_ACTIVE_DOCUMENT");
                    return "{\"success\":false,\"message\":\"No active Revit document was found.\",\"error_code\":\"NO_ACTIVE_DOCUMENT\"}";
                }

                Document doc = uidoc.Document;
                int? activeProjectId = FindProjectId(doc.Title, RevitAIApp.NormalizeFilePath(doc.PathName));
                RevitAIApp.Log("[Action] Active Project: project_id=" + (activeProjectId?.ToString() ?? "null") + " project_name=" + doc.Title);

                // Project Safety Validation
                if (targetProjectId.HasValue)
                {
                    if (!activeProjectId.HasValue || activeProjectId.Value != targetProjectId.Value)
                    {
                        RevitAIApp.Log(
                            "[Action] PROJECT_MISMATCH requested_project_id=" + targetProjectId.Value +
                            " active_project_id=" + (activeProjectId?.ToString() ?? "none"));
                        return "{\"success\":false,\"message\":\"The requested element belongs to another Revit project.\",\"error_code\":\"PROJECT_MISMATCH\"}";
                    }
                }

                if (!elementIdVal.HasValue || elementIdVal.Value <= 0)
                {
                    RevitAIApp.Log("[Action] Error: INVALID_ELEMENT_ID");
                    return "{\"success\":false,\"message\":\"Invalid Revit element ID provided.\",\"error_code\":\"INVALID_ELEMENT_ID\"}";
                }

                ElementId elemId = new ElementId(elementIdVal.Value);
                Element elem = doc.GetElement(elemId);

                if (elem == null)
                {
                    RevitAIApp.Log("[Action] Error: ELEMENT_NOT_FOUND");
                    return "{\"success\":false,\"message\":\"Element was not found in the active project.\",\"error_code\":\"ELEMENT_NOT_FOUND\"}";
                }

                // Selection & Zoom
                uidoc.Selection.SetElementIds(new System.Collections.Generic.List<ElementId> { elemId });

                if (string.Equals(normAction, "ZOOM", StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(normAction, "HIGHLIGHT", StringComparison.OrdinalIgnoreCase))
                {
                    try
                    {
                        uidoc.ShowElements(elemId);
                    }
                    catch (Exception zoomEx)
                    {
                        RevitAIApp.Log("[Action] ShowElements warning: " + zoomEx.Message);
                    }
                }

                RevitAIApp.Log("[Action] Result: SUCCESS");
                return "{\"success\":true,\"message\":\"Successfully executed " + normAction + " on element ID " + elementIdVal.Value + " (" + RevitAIApp.JsonEscape(elem.Name) + ").\"}";
            }
            catch (Exception ex)
            {
                RevitAIApp.Log("SelectOrZoomElement ERROR: " + ex);
                return "{\"success\":false,\"message\":\"Element action failed: " + RevitAIApp.JsonEscape(ex.Message) + "\",\"error_code\":\"ELEMENT_ACTION_ERROR\"}";
            }
        }

        private string OpenView(
            UIApplication app,
            string viewName,
            long? revitViewId,
            int? targetProjectId)
        {
            try
            {
                RevitAIApp.Log(
                    "OpenView() started | View: " +
                    viewName +
                    " | ViewId: " +
                    (revitViewId?.ToString() ?? "null") +
                    " | TargetProjectId: " +
                    (targetProjectId?.ToString() ?? "null"));

                UIDocument uidoc =
                    app.ActiveUIDocument;

                if (uidoc == null)
                {
                    RevitAIApp.Log(
                        "OpenView ERROR: ActiveUIDocument is null");

                    TaskDialog.Show(
                        "RevitAI",
                        "No active Revit document was found.");

                    return "{\"success\":false,\"message\":\"No active Revit document was found.\",\"error_code\":\"NO_ACTIVE_DOCUMENT\"}";
                }

                Document doc =
                    uidoc.Document;

                if (doc == null)
                {
                    RevitAIApp.Log(
                        "OpenView ERROR: Document is null");

                    TaskDialog.Show(
                        "RevitAI",
                        "No active Revit document was found.");

                    return "{\"success\":false,\"message\":\"No active Revit document was found.\",\"error_code\":\"NO_ACTIVE_DOCUMENT\"}";
                }

                RevitAIApp.Log(
                    "Active document: " +
                    doc.Title);

                string activeNormalizedPath =
                    RevitAIApp.NormalizeFilePath(doc.PathName);

                // Project Safety Validation
                if (targetProjectId.HasValue)
                {
                    int? activeProjectId =
                        FindProjectId(
                            doc.Title,
                            activeNormalizedPath);

                    if (!activeProjectId.HasValue || activeProjectId.Value != targetProjectId.Value)
                    {
                        RevitAIApp.Log(
                            "PROJECT MISMATCH ERROR: Active project (" +
                            (activeProjectId.HasValue ? activeProjectId.Value.ToString() : "unsynced/none") +
                            ") does not match requested target project (" +
                            targetProjectId.Value +
                            ").");

                        TaskDialog.Show(
                            "RevitAI Project Mismatch",
                            "The requested view belongs to another Revit project.\n\n" +
                            "Active Project: " + doc.Title + "\n" +
                            "Target Project ID: " + targetProjectId.Value);

                        return "{\"success\":false,\"message\":\"The requested view belongs to another Revit project.\",\"error_code\":\"PROJECT_MISMATCH\"}";
                    }
                }

                View foundView = null;

                // 1. Primary resolution: Search by Revit View ID
                if (revitViewId.HasValue && revitViewId.Value > 0)
                {
                    try
                    {
                        ElementId elementId = new ElementId(revitViewId.Value);
                        Element element = doc.GetElement(elementId);

                        if (element is View viewById && !viewById.IsTemplate)
                        {
                            foundView = viewById;

                            RevitAIApp.Log(
                                "Found view by ElementId: " +
                                foundView.Name +
                                " (ID: " +
                                foundView.Id.Value +
                                ")");
                        }
                    }
                    catch (Exception ex)
                    {
                        RevitAIApp.Log(
                            "GetElement by ID failed, falling back to name search: " +
                            ex.Message);
                    }
                }

                // 2. Fallback resolution: Search by view name
                if (foundView == null && !string.IsNullOrWhiteSpace(viewName))
                {
                    FilteredElementCollector collector =
                        new FilteredElementCollector(doc)
                            .OfClass(typeof(View));

                    foreach (
                        Element element in collector)
                    {
                        View view =
                            element as View;

                        if (view == null)
                        {
                            continue;
                        }

                        if (view.IsTemplate)
                        {
                            continue;
                        }

                        if (
                            string.Equals(
                                view.Name,
                                viewName,
                                StringComparison.OrdinalIgnoreCase))
                        {
                            foundView = view;

                            break;
                        }
                    }
                }

                if (foundView == null)
                {
                    RevitAIApp.Log(
                        "VIEW NOT FOUND: " +
                        (viewName ?? "Unknown View"));

                    TaskDialog.Show(
                        "RevitAI",
                        "View was not found in the active project:\n\n" +
                        (viewName ?? "Unknown View"));

                    return "{\"success\":false,\"message\":\"View was not found in the active project: " + RevitAIApp.JsonEscape(viewName ?? "Unknown View") + "\",\"error_code\":\"VIEW_NOT_FOUND\"}";
                }

                RevitAIApp.Log(
                    "VIEW FOUND: " +
                    foundView.Name +
                    " | ElementId: " +
                    foundView.Id.Value);

                try
                {
                    RevitAIApp.Log(
                        "Calling RequestViewChange for: " +
                        foundView.Name);

                    uidoc.RequestViewChange(
                        foundView);

                    RevitAIApp.Log(
                        "RequestViewChange called successfully | View: " +
                        foundView.Name);

                    return "{\"success\":true,\"message\":\"Successfully opened view: " + RevitAIApp.JsonEscape(foundView.Name) + "\"}";
                }
                catch (Exception ex)
                {
                    RevitAIApp.Log(
                        "RequestViewChange ERROR: " +
                        ex);

                    TaskDialog.Show(
                        "RevitAI View Change Error",
                        ex.ToString());

                    return "{\"success\":false,\"message\":\"RequestViewChange failed: " + RevitAIApp.JsonEscape(ex.Message) + "\",\"error_code\":\"VIEW_CHANGE_ERROR\"}";
                }
            }
            catch (Exception ex)
            {
                RevitAIApp.Log(
                    "OpenView ERROR: " +
                    ex);

                TaskDialog.Show(
                    "RevitAI OpenView Error",
                    ex.ToString());

                return "{\"success\":false,\"message\":\"OpenView failed: " + RevitAIApp.JsonEscape(ex.Message) + "\",\"error_code\":\"OPEN_VIEW_ERROR\"}";
            }
        }

        private string ExtractJsonValue(
            string json,
            string propertyName)
        {
            try
            {
                string search =
                    "\"" +
                    propertyName +
                    "\"";

                int propertyIndex =
                    json.IndexOf(
                        search,
                        StringComparison.OrdinalIgnoreCase);

                if (propertyIndex < 0)
                {
                    return "";
                }

                int colonIndex =
                    json.IndexOf(
                        ':',
                        propertyIndex + search.Length);

                if (colonIndex < 0)
                {
                    return "";
                }

                int firstQuote =
                    json.IndexOf(
                        '"',
                        colonIndex + 1);

                if (firstQuote < 0)
                {
                    return "";
                }

                int secondQuote =
                    json.IndexOf(
                        '"',
                        firstQuote + 1);

                if (secondQuote < 0)
                {
                    return "";
                }

                return json.Substring(
                    firstQuote + 1,
                    secondQuote - firstQuote - 1);
            }
            catch
            {
                return "";
            }
        }

        private long? ExtractJsonLongValue(
            string json,
            string propertyName)
        {
            try
            {
                string search =
                    "\"" +
                    propertyName +
                    "\"";

                int propertyIndex =
                    json.IndexOf(
                        search,
                        StringComparison.OrdinalIgnoreCase);

                if (propertyIndex < 0)
                {
                    return null;
                }

                int colonIndex =
                    json.IndexOf(
                        ':',
                        propertyIndex + search.Length);

                if (colonIndex < 0)
                {
                    return null;
                }

                int index = colonIndex + 1;

                while (
                    index < json.Length &&
                    (char.IsWhiteSpace(json[index]) || json[index] == '"'))
                {
                    index++;
                }

                int start = index;

                while (
                    index < json.Length &&
                    (char.IsDigit(json[index]) || json[index] == '-'))
                {
                    index++;
                }

                if (start < index)
                {
                    string numberStr =
                        json.Substring(
                            start,
                            index - start);

                    if (long.TryParse(numberStr, out long value))
                    {
                        return value;
                    }
                }
            }
            catch
            {
            }

            return null;
        }

        public string GetName()
        {
            return "RevitAI External Event Handler";
        }
    }

    // ============================================================
    // RevitAI Main Command
    // ============================================================

    [Transaction(
        TransactionMode.Manual)]
    public class RevitAICommand :
        IExternalCommand
    {
        public Result Execute(
            ExternalCommandData commandData,
            ref string message,
            ElementSet elements)
        {
            try
            {
                string appPath =
                    @"C:\Users\Hemkumar Ramesh\Documents\RevitAI";

                string pythonPath =
                    Path.Combine(
                        appPath,
                        @".venv\Scripts\python.exe");

                RevitAIApp.Log(
                    "RevitAI button clicked");

                // ====================================================
                // START FASTAPI AUTOMATICALLY
                // ====================================================

                if (!IsPortOpen("127.0.0.1", 8000, 300))
                {
                    if (!File.Exists(pythonPath))
                    {
                        TaskDialog.Show(
                            "RevitAI",
                            "Python environment was not found:\n\n" +
                            pythonPath);

                        return Result.Failed;
                    }

                    RevitAIApp.Log(
                        "FastAPI is not running. Starting backend...");

                    Process.Start(
                        new ProcessStartInfo
                        {
                            FileName = pythonPath,

                            Arguments =
                                "-m uvicorn backend.main:app --host 127.0.0.1 --port 8000",

                            WorkingDirectory = appPath,

                            UseShellExecute = false,

                            CreateNoWindow = true,

                            WindowStyle = ProcessWindowStyle.Hidden
                        });

                    RevitAIApp.Log(
                        "FastAPI start command sent");

                    Thread.Sleep(1500);
                }
                else
                {
                    RevitAIApp.Log(
                        "FastAPI already running on port 8000");
                }

                // ====================================================
                // START ELECTRON AUTOMATICALLY
                // ====================================================

                RevitAIApp.Log(
                    "Starting Electron application");

                string npmPath =
                    @"C:\Program Files\nodejs\npm.cmd";

                if (!File.Exists(npmPath))
                {
                    npmPath = "npm.cmd";
                }

                Process.Start(
                    new ProcessStartInfo
                    {
                        FileName = npmPath,

                        Arguments = "run dev",

                        WorkingDirectory = appPath,

                        UseShellExecute = false,

                        CreateNoWindow = true,

                        WindowStyle = ProcessWindowStyle.Hidden
                    });

                RevitAIApp.Log(
                    "Electron start command sent");

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                RevitAIApp.Log(
                    "RevitAICommand ERROR: " +
                    ex);

                TaskDialog.Show(
                    "RevitAI",
                    "Failed to start Electron:\n\n" +
                    ex.Message);

                return Result.Failed;
            }
        }

        private static bool IsPortOpen(
            string host,
            int port,
            int timeoutMilliseconds)
        {
            try
            {
                using (TcpClient client = new TcpClient())
                {
                    IAsyncResult result =
                        client.BeginConnect(
                            host,
                            port,
                            null,
                            null);

                    bool connected =
                        result.AsyncWaitHandle.WaitOne(
                            timeoutMilliseconds);

                    if (!connected)
                    {
                        return false;
                    }

                    client.EndConnect(result);

                    return true;
                }
            }
            catch
            {
                return false;
            }
        }
    }

    // ============================================================
    // Sync Views Command
    // ============================================================

    [Transaction(
        TransactionMode.Manual)]
    public class SyncViewsCommand :
        IExternalCommand
    {
        public Result Execute(
            ExternalCommandData commandData,
            ref string message,
            ElementSet elements)
        {
            try
            {
                RevitAIApp.Log(
                    "========================================");

                RevitAIApp.Log(
                    "Sync Views button clicked");

                UIApplication uiapp =
                    commandData.Application;

                UIDocument uidoc =
                    uiapp.ActiveUIDocument;

                if (uidoc == null)
                {
                    TaskDialog.Show(
                        "RevitAI Sync Views",
                        "No active Revit document was found.");

                    RevitAIApp.Log(
                        "Sync Views ERROR: ActiveUIDocument is null");

                    return Result.Failed;
                }

                Document doc =
                    uidoc.Document;

                if (doc == null)
                {
                    TaskDialog.Show(
                        "RevitAI Sync Views",
                        "No active Revit document was found.");

                    RevitAIApp.Log(
                        "Sync Views ERROR: Document is null");

                    return Result.Failed;
                }

                RevitAIApp.Log(
                    "Syncing document: " +
                    doc.Title);

                // ====================================================
                // Get Revit project identity
                // ====================================================

                string projectName =
                    doc.Title;

                string rawFilePath =
                    doc.PathName;

                string normalizedPath =
                    RevitAIApp.NormalizeFilePath(rawFilePath);

                RevitAIApp.Log(
                    "Project name: " +
                    projectName);

                RevitAIApp.Log(
                    "Project file path (normalized): " +
                    (normalizedPath ?? "[UNSAVED PROJECT]"));

                // ====================================================
                // Collect Revit views
                // ====================================================

                FilteredElementCollector collector =
                    new FilteredElementCollector(doc)
                        .OfClass(typeof(View));

                int viewCount = 0;

                int projectId = 0;

                using (
                    NpgsqlConnection connection =
                        new NpgsqlConnection(
                            PostgreSQLConfig.ConnectionString))
                {
                    RevitAIApp.Log(
                        "Opening PostgreSQL connection");

                    connection.Open();

                    RevitAIApp.Log(
                        "PostgreSQL connection opened");

                    using (
                        NpgsqlTransaction transaction =
                            connection.BeginTransaction())
                    {
                        try
                        {
                            // ====================================================
                            // STEP 1
                            // Find or create the Revit project
                            // ====================================================

                            projectId =
                                RevitAIExternalEventHandler.GetOrCreateProject(
                                    connection,
                                    transaction,
                                    projectName,
                                    normalizedPath);

                            RevitAIApp.Log(
                                "Project ID resolved: " +
                                projectId);

                            // ====================================================
                            // STEP 2
                            // Delete ONLY this project's old views
                            // ====================================================

                            using (
                                NpgsqlCommand deleteCommand =
                                    new NpgsqlCommand(
                                        @"DELETE FROM revit_views
                                          WHERE project_id = @project_id;",
                                        connection,
                                        transaction))
                            {
                                deleteCommand.Parameters.AddWithValue(
                                    "project_id",
                                    projectId);

                                int deletedRows =
                                    deleteCommand.ExecuteNonQuery();

                                RevitAIApp.Log(
                                    "Deleted old views for project " +
                                    projectId +
                                    ": " +
                                    deletedRows);
                            }

                            // ====================================================
                            // STEP 3
                            // Insert current Revit views
                            // ====================================================

                            foreach (
                                Element element in collector)
                            {
                                View view =
                                    element as View;

                                if (view == null)
                                {
                                    continue;
                                }

                                if (view.IsTemplate)
                                {
                                    continue;
                                }

                                string viewType =
                                    view.ViewType.ToString();

                                string description =
                                    RevitAIExternalEventHandler.BuildViewDescription(
                                        view);

                                using (
                                    NpgsqlCommand insertCommand =
                                        new NpgsqlCommand(
                                            @"INSERT INTO revit_views
                                              (
                                                  revit_view_id,
                                                  name,
                                                  view_type,
                                                  description,
                                                  level_name,
                                                  project_id
                                              )
                                              VALUES
                                              (
                                                  @revit_view_id,
                                                  @name,
                                                  @view_type,
                                                  @description,
                                                  @level_name,
                                                  @project_id
                                              );",
                                            connection,
                                            transaction))
                                {
                                    insertCommand.Parameters.AddWithValue(
                                        "revit_view_id",
                                        view.Id.Value);

                                    insertCommand.Parameters.AddWithValue(
                                        "name",
                                        view.Name);

                                    insertCommand.Parameters.AddWithValue(
                                        "view_type",
                                        viewType);

                                    insertCommand.Parameters.AddWithValue(
                                        "description",
                                        description);

                                    string levelName =
                                        RevitAIExternalEventHandler.GetViewLevelName(view);

                                    if (string.IsNullOrWhiteSpace(levelName))
                                    {
                                        insertCommand.Parameters.AddWithValue(
                                            "level_name",
                                            DBNull.Value);
                                    }
                                    else
                                    {
                                        insertCommand.Parameters.AddWithValue(
                                            "level_name",
                                            levelName);
                                    }

                                    insertCommand.Parameters.AddWithValue(
                                        "project_id",
                                        projectId);

                                    insertCommand.ExecuteNonQuery();
                                }

                                viewCount++;

                                RevitAIApp.Log(
                                    "Synced view | " +
                                    view.Name +
                                    " | Type: " +
                                    viewType +
                                    " | ElementId: " +
                                    view.Id.Value +
                                    " | ProjectId: " +
                                    projectId);
                            }

                            // ====================================================
                            // STEP 4
                            // Commit everything
                            // ====================================================

                            transaction.Commit();

                            RevitAIApp.Log(
                                "PostgreSQL transaction committed");
                        }
                        catch
                        {
                            transaction.Rollback();

                            RevitAIApp.Log(
                                "PostgreSQL transaction rolled back");

                            throw;
                        }
                    }

                    connection.Close();

                    RevitAIApp.Log(
                        "PostgreSQL connection closed");
                }

                RevitAIApp.Log(
                    "Total views synchronized: " +
                    viewCount);

                RevitAIApp.Log(
                    "Sync Views completed successfully");

                TaskDialog.Show(
                    "RevitAI Sync Views",
                    "Project synchronization completed successfully.\n\n" +
                    "Project:\n" +
                    projectName +
                    "\n\n" +
                    "Project ID:\n" +
                    projectId +
                    "\n\n" +
                    "Views synchronized:\n" +
                    viewCount);

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                RevitAIApp.Log(
                    "Sync Views ERROR: " +
                    ex);

                TaskDialog.Show(
                    "RevitAI Sync Views Error",
                    ex.ToString());

                message =
                    ex.Message;

                return Result.Failed;
            }
        }

    }
}