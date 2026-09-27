<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Supplier extends Model
{
    protected $fillable = ['name', 'phone', 'address'];

    public function payables()
    {
        return $this->hasMany(AccountsPayable::class);
    }

    /** Sisa hutang belum dibayar ke distributor ini */
    public function outstandingPayable(): float
    {
        return (float) $this->payables()->where('status', 'unpaid')->sum('amount');
    }
}
