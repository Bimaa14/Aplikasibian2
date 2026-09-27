<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Expense extends Model
{
    protected $fillable = ['date', 'amount', 'category', 'description'];

    protected $casts = ['date' => 'date', 'amount' => 'float'];
}
