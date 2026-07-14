@echo off
echo Updating returned orders...
cd /d "C:\Users\mujir\shadankhanfurnex\shadanfurnex\furnex_final_review\furnex_final"
python manage.py update_returned_orders
echo Done!
pause
