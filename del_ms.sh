rm ms_delete_cmd_lines.bat
redis-cli -h ms-node-01 --scan --pattern '*pchome_opp*' >> ms_delete_cmd_lines.bat
sed -i "s/\[/redis-cli\ -h\ ms-node-01\ del\ '\[/g" ms_delete_cmd_lines.bat
sed -i "s/\]/\]'/g" ms_delete_cmd_lines.bat
sh ms_delete_cmd_lines.bat
 
