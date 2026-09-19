using System;

namespace RevitPlugin
{
    internal static class PostgreSQLConfig
    {
        public static string ConnectionString
        {
            get
            {
                string password =
                    Environment.GetEnvironmentVariable("REVITAI_DB_PASSWORD");

                if (string.IsNullOrWhiteSpace(password))
                {
                    throw new InvalidOperationException(
                        "REVITAI_DB_PASSWORD environment variable is not set."
                    );
                }

                return
                    "Host=127.0.0.1;" +
                    "Port=5432;" +
                    "Database=revitai;" +
                    "Username=postgres;" +
                    $"Password={password};";
            }
        }
    }
}
