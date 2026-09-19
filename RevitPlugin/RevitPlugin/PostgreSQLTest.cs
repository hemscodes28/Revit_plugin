using System;
using Npgsql;

namespace RevitPlugin
{
    internal static class PostgreSQLTest
    {
        public static string TestConnection()
        {
            try
            {
                using (NpgsqlConnection connection =
                    new NpgsqlConnection(PostgreSQLConfig.ConnectionString))
                {
                    connection.Open();

                    return "SUCCESS: Connected to PostgreSQL database 'revitai'.";
                }
            }
            catch (Exception ex)
            {
                return "FAILED: " + ex.Message;
            }
        }
    }
}